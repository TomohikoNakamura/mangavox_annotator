
const HELP_DESCRIPTION = `
  <h5>Help: Keyboard Shortcuts</h5>
  <ul>
    <li><strong>Space:</strong> Play/Pause audio</li>
    <li><strong>Press n:</strong> Select next region</li>
    <li><strong>Press b:</strong> Select previous region</li>
    <li><strong>Press s:</strong> Save the selected region</li>
    <li><strong>Press r:</strong> Reset the selected region</li>
    <li><strong>Mouse wheel:</strong> Zoom in/out the waveform</li>
    <li><strong>Click the waveform:</strong> Deselect the current region</li>
    <li><strong>Click the region:</strong> Select the clicked region</li>
    <li><strong>Click the canvas:</strong> Select the image annotation containing the coordinate position of the mouse when a region is selected. If the position is included in multiple annotations, the minimum-area annotation is selected.</li>
    <li><strong>Press h:</strong> Show/hide this help message</li>
  </ul>
  <p>Select a region by using the keyboard shortcuts or clicking directly on the waveform.</p>
  <p>Annotation Colors: <span style="color: rgba(0, 123, 255, 1);">Texts</span>, <span style="color: rgba(40, 167, 69, 1);">Frames</span>, <span style="color: rgba(255, 193, 7, 1);">Bodies</span>, <span style="color: rgba(220, 53, 69, 1);">Faces</span></p>
  <h5>Remarks</h5>
  <p>Rectangles of broken lines are unassigned frame/face/body/text elements of Manga109.</p>
`;

/**
 * マンガアノテーションツールのメインクラス
 */
class MangaAnnotationTool {
  // シングルトンインスタンス
  static instance = null;

  constructor() {
    if (MangaAnnotationTool.instance) {
      return MangaAnnotationTool.instance;
    }
    // 初期化処理
    this.setupState();
    this.setup();
    // シングルトンインスタンスを設定
    MangaAnnotationTool.instance = this;
  }

  /**
   * 遷移状態関連のセットアップ
   * アノテーションの状態管理にプロキシを利用．
   */
  setupState() {
    this.state = new Proxy(
      {
        zoomLevel: 50, // ズームレベルの初期値
        selectedRegion: null, // 選択された音声アノテーション
        activeRegions: [], // 現在アクティブな音声アノテーション
      },
      {
        set: (target, key, value) => {
          if (key === "zoomLevel" && target[key] !== value) {
            // zoom levelが変更された場合は、waveformをズーム
            value = Math.min(200, Math.max(10, parseInt(value, 10)));
            target[key] = value;
            this.waveSurfer.zoom(value);
          } else if (key == "selectedRegion" && target[key] !== value) {
            if (target[key] != null) {
              this.saveAnnotation(target[key]).then(() => {
                target[key] = value;
                this.setEditElementsEnabled(value != null);
                this.selectAudioRegion(value);
              });
            } else {
              // 選択されたリージョンが変更された場合は、詳細を表示
              target[key] = value;
              this.setEditElementsEnabled(value != null);
              this.selectAudioRegion(value);
            }
          } else if (key == "activeRegions" && target[key] !== value) {
            // 対象のアノテーションをハイライト
            if (value.length == 0) {
              this.writeAnnotationDetails(null);
              this.imageManager.drawImageAnnotations([]);
            } else {
              this.writeAnnotationDetails(value[0].annotation);
              this.imageManager.drawImageAnnotations(value.map((region) => region.annotation));
            }
            //
            target[key] = value;
          }
          return true;
        }
      }
    );
  }

  /**
   * 当該インスタンスのセットアップ
   */
  setup() {
    // 画像管理クラスのインスタンスを作成
    this.imageManager = new ImageManager();
    // 音声アノテーションの初期化
    this.annotations = [];
    // キャラクターの初期化
    this.audioCharacters = []; // 音声アノテーションに登場するキャラクターのリスト
    this.activeAudioCharacters = []; // 現在選択されている音声アノテーションと，発話時刻が重複しているものがあるキャラクターのリスト
    this.characters = []; // 全てのキャラクターのリスト（画像のみに登場するものも含む）
    this.actors = []; // 演技者のリスト
    // WaveSurferのインスタンスを作成
    this.waveSurfer = null;
    // this.waveSurferInstances = []; TODO: キャラ毎の音声ファイルの場合への対応
    this.styles = {
      normal: "rgba(0, 123, 255, 0.3)", // 通常
      toBeFixed: "rgba(255, 123, 0, 0.5)", // 何らかの修正が必要な場合
    };
  }

  /**
   * セットアップが終わった後の初期化処理
   */
  async initialize() {
    this.setOverlayState(true, "Preparing, please wait...", true); // オーバーレイを表示  
    try {
      // 画像読み込み，アノテーション読み込み，オーディオ読み込み，Regionの描画
      await Promise.all([this.imageManager.initialize(), this.loadVoiceAnnotation(), this.loadCharacters(), this.loadAudioCharacters(), this.loadActors(), this.loadAudio()]);
    } catch (error) {
      this.setOverlayState(true, error.message); // エラーメッセージを表示
    }
    // // フィルターを初期化
    // this.initializeFilter();
    // イベントリスナーを設定
    this.setupEventListeners();
    this.imageManager.setupEventListeners();
    // 画像上にアノテーションを描画
    this.imageManager.drawImageAnnotations([]);
    // 編集要素を無効化
    this.setEditElementsEnabled(false);
    // オーディオ読み込み完了後にオーバーレイを非表示
    this.setOverlayState(false, "");
  }

  // /** TODO
  //  * フィルタ処理を行うための初期化
  //  */
  // initializeFilter() {
  //   // フィルタ関連の要素を取得
  //   const abnormalityFilterCheckbox = document.getElementById("abnormality_filter");
  //   const voiceFilterInput = document.getElementById("voice_filter");
  //   const audioFilterSelect = document.getElementById("audio_id_filter");
  //   const actorFilterSelect = document.getElementById("actor_id_filter");
  //   const characterFilterSelect = document.getElementById("character_id_filter");
  //   const noteFilterCheckbox = document.getElementById("annotation_note_filter");
  //   const commentFilterCheckbox = document.getElementById("annotation_comment_filter");
  //   // audio IDフィルター用に音声キャラクターを設定
  //   audioFilterSelect.innerHTML = '<option value="">All</option>';
  //   this.audioCharacters.forEach((audioCharacter) => {
  //     const option = document.createElement("option");
  //     option.value = audioCharacter;
  //     option.text = audioCharacter;
  //     audioFilterSelect.appendChild(option);
  //   });
  //   // actor IDフィルター用に俳優を設定
  //   actorFilterSelect.innerHTML = '<option value="">All</option>';
  //   this.actors.forEach((actor) => {
  //     const option = document.createElement("option");
  //     option.value = actor;
  //     option.text = actor;
  //     actorFilterSelect.appendChild(option);
  //   });
  //   // character IDフィルター用にキャラクターを設定
  //   characterFilterSelect.innerHTML = '<option value="">All</option>';
  //   this.characters.forEach((character) => {
  //     const option = document.createElement("option");
  //     option.value = character.id;
  //     option.text = character.name;
  //     characterFilterSelect.appendChild(option);
  //   });
  //   // イベントリスナーを設定
  //   [abnormalityFilterCheckbox, voiceFilterInput, audioFilterSelect, actorFilterSelect, characterFilterSelect, noteFilterCheckbox, commentFilterCheckbox].forEach((input) => {
  //     input.addEventListener("input", () => { this.filterAnnotations(); });
  //   });
  //   // 初期状態では全てのアノテーションを表示
  //   this.activeAnnotationIndices = this.annotations.map((annotation, index) => index);
  // }

  /**
   * 音声キャラクターを読み込む
   * @param {string} voice_id 
   */
  async loadAudioCharacters(voice_id = null) {
    if (voice_id) {
      // voice_idが指定されている場合は、その音声キャラクターのみを読み込む
      try {
        const response = await fetch(`/audio_characters/${voice_id}`);
        if (!response.ok) {
          throw new Error(`Failed to fetch audio characters: ${response.statusText}`);
        }
        const data = await response.json();
        this.activeAudioCharacters = data; // 現在の音声アノテーションと発話時刻が重複しているキャラクターのリスト
      } catch (error) {
        console.error("Error loading audio characters:", error);
        throw error;
      }
    } else {
      // voice_idが指定されていない場合は、全ての音声キャラクターを読み込む
      try {
        const response = await fetch(`/audio_characters`);
        if (!response.ok) {
          throw new Error(`Failed to fetch audio characters: ${response.statusText}`);
        }
        const data = await response.json();
        this.audioCharacters = data;
      } catch (error) {
        console.error("Error loading audio characters:", error);
        throw error;
      }
    }
  }

  /**
   * 音声ファイルを読み込む
   */
  async loadAudio() {
    try {
      // WaveSurferの初期化
      this.initializeWaveSurfer();
      await this.waveSurfer.load("/audio");
    } catch (error) {
      console.error("Error loading audio:", error);
      throw error;
    }
  }

  /**
   * WaveSurferの初期化
   */
  initializeWaveSurfer() {
    // WaveSurferのインスタンスを作成
    this.waveSurfer = WaveSurfer.create({
      container: "#waveform",
      waveColor: "#6c757d",
      progressColor: "#0d6efd",
      cursorColor: "#dc3545",
      barWidth: 3,
      height: 128,
      pixelRatio: 1,
      responsive: true,
      normalize: true,
      backend: "MediaElement",
      partialRender: true,
      scrollParent: true,
      mediaControls: true,
      plugins: [
        WaveSurfer.Minimap.create({
          container: '#minimap', // ミニマップを表示する要素
          height: 50, // ミニマップの高さ
          waveColor: '#ddd', // ミニマップの波形色
          progressColor: '#999' // ミニマップの進捗波形色
        }),
        WaveSurfer.Regions.create(),
      ],
    });

    // 波形の準備ができたときのイベントを設定
    this.waveSurfer.on("ready", () => {
      const progressBar = document.getElementById("waveform_progress_bar");
      progressBar.style.width = "100%";
      this.waveSurfer.zoom(this.state.zoomLevel); // デフォルトのズーム値を適用
      this.drawAudioRegions(); // 音声区間の描画
      progressBar.classList.remove("progress-bar-animated");
      progressBar.style.display = "none";
    });

    // 波形全体のクリックイベントを設定
    this.waveSurfer.on("click", (event) => {
      this.state.selectedRegion = null;
    });

    // 波形の読み込み進捗を表示
    this.waveSurfer.on("loading", (progress) => {
      const progressBar = document.getElementById("waveform_progress_bar");
      progressBar.style.width = `${progress}%`;
      progressBar.setAttribute("aria-valuenow", progress);
    });

    // 波形の再生位置を監視
    this.waveSurfer.on("audioprocess", () => {
      const currentTime = this.waveSurfer.getCurrentTime();
      if (this.state.selectedRegion && currentTime >= this.state.selectedRegion.end) {
        // 再生位置をリージョンの開始位置に戻す
        this.waveSurfer.pause();
        this.waveSurfer.seekTo(this.state.selectedRegion.start / this.waveSurfer.getDuration());
      }
      if (this.state.selectedRegion == null) {
        // 再生中のリージョンを特定
        this.state.activeRegions = this.getAudioRegionByTime(currentTime);
      }
    });

    // 再生している間は編集を無効化
    this.waveSurfer.on("play", () => {
      this.setEditElementsEnabled(false);
    });
    this.waveSurfer.on("pause", () => {
      // 再生が一時停止されたら、選択されたリージョンがあれば編集を有効化
      if (this.state.selectedRegion != null) {
        this.setEditElementsEnabled(true);
      }
    });
    this.waveSurfer.on("finish", () => {
      // 再生が終了したら、選択されたリージョンがあれば編集を有効化
      if (this.state.selectedRegion != null) {
        this.setEditElementsEnabled(true);
      }
    });
  }

  /**
   * 音声アノテーションを読み込む
   * @param {string} targetVoiceID 
   * @return {Promise<void>}
   */
  async loadVoiceAnnotation(targetVoiceID = "all") {
    try {
      const response = await fetch(`/annotations/voice/${targetVoiceID}`);
      if (!response.ok) {
        throw new Error(`Failed to fetch annotations: ${response.statusText}`);
      }
      const data = await response.json();
      if (targetVoiceID === "all") {
        // 全てのアノテーションを読み込む
        this.annotations = data;
      } else {
        // 対象のアノテーションを更新
        this.annotations = this.annotations.map((annotation) => {
          if (annotation.id === targetVoiceID) {
            return data;
          }
          return annotation;
        });
        // 対象の音声区間を更新
        const regionsPlugin = this.getRegionsPlugin();
        for (let i = 0; i < regionsPlugin.regions.length; i++) {
          if (regionsPlugin.regions[i].annotation.id === targetVoiceID) {
            regionsPlugin.regions[i].annotation = data;
            break;
          }
        }
      }
    } catch (error) {
      console.error("Error loading annotations:", error);
      throw error;
    }
  }

  /**
   * キャラクターを読み込む
   * @returns {Promise<void>}
   */
  async loadCharacters() {
    try {
      const response = await fetch("/annotations/characters");
      if (!response.ok) {
        throw new Error(`Failed to fetch characters: ${response.statusText}`);
      }
      const data = await response.json();
      this.characters = data;
    } catch (error) {
      console.error("Error loading characters:", error);
      throw error;
    }
  }

  /**
   * 演技者を読み込む
   * @returns {Promise<void>}
   */
  async loadActors() {
    try {
      const response = await fetch("/actors");
      if (!response.ok) {
        throw new Error(`Failed to fetch actors: ${response.statusText}`);
      }
      const data = await response.json();
      this.actors = data;
    } catch (error) {
      console.error("Error loading actors:", error);
      throw error;
    }
  }

  /**
   * オーバーレイの表示状態を設定
   * @param {boolean} isVisible 
   * @param {string} message 
   * @param {boolean} isHelp 
   */
  setOverlayState(isVisible, message = "", isHelp = false) {
    const overlay = document.getElementById("overlay");
    const statusMessage = document.getElementById("status");
    if (overlay && statusMessage) {
      overlay.style.display = isVisible ? "flex" : "none"; // オーバーレイを表示・非表示
      statusMessage.textContent = message; // メッセージを更新
      if (isHelp) {
        document.getElementById("help_message").innerHTML = HELP_DESCRIPTION; // ヘルプを表示
      }
    }
  }

  /**
   * ヘルプメッセージの表示・非表示を切り替える
   */
  toggleHelp() {
    const overlay = document.getElementById("overlay");
    const helpMessage = document.getElementById("help_message");
    if (overlay.style.display === "flex") {
      overlay.style.display = "none"; // オーバーレイを非表示
    } else {
      overlay.style.display = "flex"; // オーバーレイを表示
      helpMessage.innerHTML = HELP_DESCRIPTION; // ヘルプを表示
    }
  }

  /**
   * 編集要素を有効化・無効化する
   * @param {boolean} enabled - 有効化するかどうか
   */
  setEditElementsEnabled(enabled) {
    ["actor_id", "spoken_text", "text_id", "page_index", "frame_id", "body_id", "face_id", "character_id", "annotation_comment"].forEach((elementId) => {
      document.getElementById(elementId).disabled = !enabled;
    });
    document.getElementById("audio_id").disabled = true; // 音声IDは編集不可
  }

  //////////////////////////
  // Audio region methods //
  //////////////////////////
  /**
   * Regionsプラグインを取得
   * @return {WaveSurfer.Regions} - アクティブなRegionsプラグイン
   * */
  getRegionsPlugin() {
    const regionsPlugin = this.waveSurfer.getActivePlugins().find(
      (plugin) => plugin instanceof WaveSurfer.Regions
    );

    if (!regionsPlugin) {
      console.error("Regions plugin is not active.");
      return;
    }
    return regionsPlugin;
  }

  /**
   * アノテーションが正常かどうかをチェック
   * @param {Object} annotation - アノテーションオブジェクト
   * @returns {boolean} - 正常な場合はtrue, 異常な場合はfalse
   */
  isVoiceAnnotationNormal(annotation) {
    // 必須フィールドをチェック
    if (annotation.audio_id == null) {
      return false;
    }
    if (annotation.actor_id == null) {
      return false;
    }
    if (annotation.character_id == null) {
      return false;
    }
    if (annotation.page_index == null) {
      return false;
    }
    // 複数IDが含まれているか（カンマ区切りで複数指定されているか）をチェック
    if (annotation.face_id && annotation.face_id.includes(",")) {
      return false;
    }
    if (annotation.frame_id && annotation.frame_id.includes(",")) {
      return false;
    }
    if (annotation.body_id && annotation.body_id.includes(",")) {
      return false;
    }
    return true;
  }

  /**
   * 音声アノテーションのリージョンを描画（一度だけ呼ばれる）
   * @param {Object[]} annotations - 音声アノテーションの配列
   */
  drawAudioRegions() {
    const regionsPlugin = this.getRegionsPlugin();

    // 既存のリージョンをクリア
    regionsPlugin.clearRegions();

    // リージョンを描画
    this.annotations.forEach((annotation) => {
      const region = regionsPlugin.addRegion({
        start: annotation.start,
        end: annotation.end,
        color: this.isVoiceAnnotationNormal(annotation) ? this.styles.normal : this.styles.toBeFixed,
        drag: false,
        resize: false
      });

      // カスタムデータとしてアノテーションを関連付け
      region.annotation = annotation;

      // Regionにクリックイベントを登録
      region.element.addEventListener("click", (event) => {
        event.stopPropagation(); // 波形のクリックイベントを無効化
        this.state.selectedRegion = region;
      });

      // start, endが変更されたらアノテーションを更新
      region.on("update", () => {
        region.annotation.start = region.start;
        region.annotation.end = region.end;
        region.annotation["isChanged"] = true;
      });
    });
  }

  /**
   * アノテーションの詳細を表示
   * @param {Object} annotation - アノテーションオブジェクト
   */
  writeAnnotationDetails(annotation) {
    // 共通処理
    {
      let targetAnnotation = null;
      if (annotation) {
        // 何もしない場合は，annotationをそのまま使用
        targetAnnotation = annotation;
      } else {
        targetAnnotation = {
          "text": "",
          "start": "None",
          "end": "None",
          "note": { "text": null },
          "page_index": null,
          "text_id": null,
          "frame_id": null,
          "body_id": null,
          "face_id": null,
          "character_name": null,
          "character_id": null,
          "annotation_comment": null,
          "audio_id": null,
        };
      }
      // 表示専用フィールドをセット
      ["voice_id", "start", "end", "note"].forEach((voiceKey) => {
        if (voiceKey == "voice_id") {
          document.getElementById(`current_${voiceKey}`).textContent = targetAnnotation.id;
        } else if (voiceKey === "note") {
          document.getElementById(voiceKey).value = targetAnnotation[voiceKey].text || "";
        } else {
          document.getElementById(`current_${voiceKey}`).textContent = targetAnnotation[voiceKey] + "s";
        }
      });

      // 現在の値をセット
      ["actor_id", "audio_id", "page_index", "text_id", "frame_id", "body_id", "face_id"].forEach((voiceKey) => {
        const targetElement = document.getElementById(`current_${voiceKey}`);
        targetElement.textContent = targetAnnotation[voiceKey] != null ? targetAnnotation[voiceKey] : "Empty";
        if (voiceKey === "page_index" || voiceKey === "audio_id" || voiceKey === "actor_id") {
          if (targetAnnotation[voiceKey] != null) {
            targetElement.style.backgroundColor = null;
          } else {
            targetElement.style.backgroundColor = this.styles.toBeFixed;
          }
        } else {
          if (targetAnnotation[voiceKey] != null && !targetAnnotation[voiceKey].includes(",")) {
            targetElement.style.backgroundColor = null;
          } else {
            targetElement.style.backgroundColor = this.styles.toBeFixed;
          }
        }
      });
      if (targetAnnotation.character_id) {
        document.getElementById("current_character_id").textContent = `${targetAnnotation.character_name} (${targetAnnotation.character_id})`;
        document.getElementById("current_character_id").style.backgroundColor = null;
      } else {
        document.getElementById("current_character_id").textContent = null;
        document.getElementById("current_character_id").style.backgroundColor = this.styles.toBeFixed;
      }
      ["annotation_comment", "spoken_text"].forEach((voiceKey) => {
        if (voiceKey === "spoken_text") {
          document.getElementById(voiceKey).value = targetAnnotation.text || "";
        } else {
          document.getElementById(voiceKey).value = targetAnnotation[voiceKey] ? targetAnnotation[voiceKey].text : "";
        }
      });
    }// ここでtargetAnnotationがスコープ外になる

    if (annotation) {
      // 編集要素のプルダウンメニューリストを更新
      const createOption = (value, text) => {
        const option = document.createElement("option");
        option.value = value;
        option.text = text;
        return option;
      }
      {
        const page = this.imageManager.imageAnnotations[annotation.page_index || this.imageManager.state.currentPage];
        [["texts", "text_id"], ["frames", "frame_id"], ["bodies", "body_id"], ["faces", "face_id"]].forEach(([imageKey, voiceKey]) => {
          document.getElementById(voiceKey).innerHTML = "";
          // imageKeyがframes, faces, bodies以外の場合は空のオプションを追加
          if (imageKey !== "frames" && imageKey !== "faces" && imageKey !== "bodies") {
            document.getElementById(voiceKey).add(createOption(null, ""));
          }
          page[imageKey].forEach((candidate) => {
            let candidateText = "";
            if (imageKey === "bodies" || imageKey === "faces") {
              // キャラクタ名を取得
              const characterName = this.characters.find((character) => character.id === candidate.character).name;
              candidateText = `${candidate.id} (${characterName})`;
            } else {
              candidateText = candidate.id;
            }
            document.getElementById(voiceKey).add(createOption(candidate.id, candidateText));
          });
        });
      } // pageのスコープ終了

      // キャラクタ名のプルダウンメニューリストを更新，audio_idのプルダウンメニューリストを更新
      [[this.characters, "character_id"], [this.activeAudioCharacters, "audio_id"], [this.actors, "actor_id"]].forEach(([candidates, voiceKey]) => {
        document.getElementById(voiceKey).innerHTML = "";
        candidates.forEach((candidate) => {
          if (voiceKey == "character_id") {
            document.getElementById(voiceKey).add(createOption(candidate.id, candidate.name));
          } else {
            document.getElementById(voiceKey).add(createOption(candidate, candidate));
          }
        });
      });

      // プルダウンメニューを初期化
      const initializeDropdown = (elementId, value) => {
        if (elementId === "frame_id" || elementId === "face_id" || elementId === "body_id") {
          const selectElement = document.getElementById(elementId);
          const selectedValues = value ? value.split(",") : [];
          Array.from(selectElement.options).forEach(option => {
            if (selectedValues.includes(option.value)) {
              option.selected = true;
            }
          });
        } else {
          // valueがnullまたは,を含む場合は空文字にする
          if (value == null || value.includes(",")) {
            document.getElementById(elementId).value = "";
          } else {
            document.getElementById(elementId).value = value;
          }
        }
      };
      document.getElementById("page_index").value = annotation.page_index != null ? annotation.page_index : "";
      initializeDropdown("frame_id", annotation.frame_id);
      initializeDropdown("body_id", annotation.body_id);
      initializeDropdown("face_id", annotation.face_id);
      initializeDropdown("text_id", annotation.text_id);
      initializeDropdown("audio_id", annotation.audio_id);
      initializeDropdown("actor_id", annotation.actor_id);
      {
        // this.charactersからannotation.character_idに一致するものを取得
        const character = this.characters.find((candidate) => candidate.id === annotation.character_id);
        initializeDropdown("character_id", character.id);
      }
    } else {
      // アノテーションがない場合は、全ての編集要素を空にする
      // 編集要素のプルダウンメニューリストを更新
      ["actor_id", "audio_id", "text_id", "frame_id", "body_id", "face_id", "character_id"].forEach((voiceKey) => {
        document.getElementById(voiceKey).innerHTML = "";
      });
      ["annotation_comment", "spoken_text"].forEach((voiceKey) => {
        document.getElementById(voiceKey).value = "";
      });
    }
  };

  // writeAnnotationDetails(annotation) {
  //   {
  //     let targetAnnotation = null;
  //     if (annotation) {
  //       // nothing to do
  //       targetAnnotation = annotation;
  //     } else {
  //       targetAnnotation = {
  //         "text": "",
  //         "start": "None",
  //         "end": "None",
  //         "note": { "text": null },
  //         "page_index": null,
  //         "text_id": null,
  //         "frame_id": null,
  //         "body_id": null,
  //         "face_id": null,
  //         "character_name": null,
  //         "character_id": null,
  //         "annotation_comment": null,
  //       };
  //     }
  //     // 表示専用フィールドをセット
  //     document.getElementById("unchangeable_voice_properties_display").innerHTML = `
  //       <strong style="color: ${this.imageManager.styles.texts.getStyle(1)}">Text:</strong> ${targetAnnotation.text} (${targetAnnotation.text_id || ""}) <br>
  //       <strong>Start:</strong> ${targetAnnotation.start} s, <strong>End:</strong> ${targetAnnotation.end} s <br>
  //       <strong>Actor ID:</strong> ${targetAnnotation.actor_id} <br>
  //       <strong>Note:</strong> ${targetAnnotation.note.text || ""}
  //     `;

  //     // 現在の値をセット
  //     ["page_index", "text_id", "frame_id", "body_id", "face_id"].forEach((voiceKey) => {
  //       const targetElement = document.getElementById(`current_${voiceKey}`);
  //       targetElement.textContent = targetAnnotation[voiceKey] != null ? targetAnnotation[voiceKey] : "Empty";
  //       if (voiceKey == "page_index") {
  //         if (targetAnnotation[voiceKey] != null) {
  //           targetElement.style.backgroundColor = null;
  //         } else {
  //           targetElement.style.backgroundColor = this.styles.toBeFixed;
  //         }
  //       } else {
  //         if (targetAnnotation[voiceKey] != null && !targetAnnotation[voiceKey].includes(",")) {
  //           targetElement.style.backgroundColor = null;
  //         } else {
  //           targetElement.style.backgroundColor = this.styles.toBeFixed;
  //         }
  //       }
  //     });
  //     if (targetAnnotation.character_id) {
  //       document.getElementById("current_character_id").textContent = `${targetAnnotation.character_name} (${targetAnnotation.character_id})`;
  //       document.getElementById("current_character_id").style.backgroundColor = null;
  //     } else {
  //       document.getElementById("current_character_id").textContent = null;
  //       document.getElementById("current_character_id").style.backgroundColor = this.styles.toBeFixed;
  //     }
  //     const commentTextarea = document.getElementById('annotation_comment');
  //     if (targetAnnotation.annotation_comment) {
  //       commentTextarea.value = targetAnnotation.annotation_comment.text;
  //     } else {
  //       commentTextarea.value = "";
  //     }
  //   }// ここでtargetAnnotationがスコープ外になる

  //   if (annotation) {
  //     // 編集要素のプルダウンメニューリストを更新
  //     const createOption = (value, text) => {
  //       const option = document.createElement("option");
  //       option.value = value;
  //       option.text = text;
  //       return option;
  //     }
  //     const page = this.imageManager.imageAnnotations[annotation.page_index || this.imageManager.state.currentPage];
  //     [["texts", "text_id"], ["frames", "frame_id"], ["bodies", "body_id"], ["faces", "face_id"]].forEach(([imageKey, voiceKey]) => {
  //       document.getElementById(voiceKey).innerHTML = "";
  //       // framesは複数選択可能なので，それ以外に関してはnullを選択できるように設定
  //       if (imageKey !== "frames" && imageKey !== "faces" && imageKey !== "bodies") {
  //         document.getElementById(voiceKey).add(createOption(null, ""));
  //       }
  //       page[imageKey].forEach((candidate) => {
  //         let candidateText = "";
  //         if (imageKey === "bodies" || imageKey === "faces") {
  //           // キャラクタ名を取得
  //           const characterName = this.characters.find((character) => character.id === candidate.character).name;
  //           candidateText = `${candidate.id} (${characterName})`;
  //         } else {
  //           candidateText = candidate.id;
  //         }
  //         document.getElementById(voiceKey).add(createOption(candidate.id, candidateText));
  //       });
  //     });
  //     {
  //       const voiceKey = "character_id";
  //       document.getElementById(voiceKey).innerHTML = "";
  //       this.characters.forEach((candidate) => {
  //         document.getElementById(voiceKey).add(createOption(candidate.id, candidate.name));
  //       });
  //     }

  //     // プルダウンメニューを初期化
  //     const initializeDropdown = (elementId, value) => {
  //       // document.getElementById(elementId).value = value ? value.split(",")[0]:"";
  //       if (elementId === "frame_id" || elementId === "face_id" || elementId === "body_id") {
  //         const selectElement = document.getElementById(elementId);
  //         const selectedValues = value ? value.split(",") : [];
  //         Array.from(selectElement.options).forEach(option => {
  //           if (selectedValues.includes(option.value)) {
  //             option.selected = true;
  //           }
  //         });
  //       } else {
  //         // valueがnullまたは,を含む場合は空文字にする
  //         if (value == null || value.includes(",")) {
  //           document.getElementById(elementId).value = "";
  //         } else {
  //           document.getElementById(elementId).value = value;
  //         }
  //       }
  //     };
  //     document.getElementById("page_index").value = annotation.page_index != null ? annotation.page_index : "";
  //     initializeDropdown("frame_id", annotation.frame_id);
  //     initializeDropdown("body_id", annotation.body_id);
  //     initializeDropdown("face_id", annotation.face_id);
  //     initializeDropdown("text_id", annotation.text_id);
  //     // this.charactersからannotation.character_idに一致するものを取得
  //     const character = this.characters.find((candidate) => candidate.id === annotation.character_id);
  //     initializeDropdown("character_id", character.id);
  //   } else {
  //     // 編集要素のプルダウンメニューリストを更新
  //     ["text_id", "frame_id", "body_id", "face_id", "character_id"].forEach((voiceKey) => {
  //       document.getElementById(voiceKey).innerHTML = "";
  //     });
  //     const commentTextarea = document.getElementById('annotation_comment');
  //     commentTextarea.value = "";
  //   }
  // };

  /**
   * 選択された音声リージョンを設定
   * @param {WaveSurfer.Region} region - 選択されたリージョン
   */
  selectAudioRegion(region) {
    // 画像にアノテーションを描画 & ページも更新
    this.imageManager.drawImageAnnotations(region ? [region.annotation] : []);
    if (region) {
      // 再生位置を選択したRegionの開始位置に設定
      this.waveSurfer.seekTo(region.start / this.waveSurfer.getDuration());
    }
    // 選択されたリージョンの詳細を表示
    this.writeAnnotationDetails(region ? region.annotation : null);
    // 色を更新
    if (region != null) {
      region.element.style.backgroundColor = this.isVoiceAnnotationNormal(region.annotation) ? this.styles.normal : this.styles.toBeFixed;
    }
    // 選択されたリージョンを更新
    this.toggleVoiceEditability();
  }

  /**
   * 音声リージョンの編集可能状態を切り替える
   */
  toggleVoiceEditability() {
    // voiceのstart, endを変更できるようにする.
    const voiceEditModeToggle = document.getElementById("voice_edit_mode_toggle");
    for (const region of this.getRegionsPlugin().regions) {
      if (this.state.selectedRegion !== null && (region.annotation.id === this.state.selectedRegion.annotation.id)) {
        region.setOptions({ "resize": voiceEditModeToggle.checked });
      } else {
        region.setOptions({ "resize": false });
      }
    }
  }

  /**
   * 現在の再生位置に最も近い音声リージョンを取得
   * @param {number} time - 再生位置の時間（秒）
   * @returns {WaveSurfer.Region[]} - 現在の再生位置に最も近い音声リージョンの配列
   */
  getAudioRegionByTime(time) {
    const regionsPlugin = this.getRegionsPlugin();

    if (!regionsPlugin) return [];

    const regions = regionsPlugin.regions;
    return regions.filter((region) => time >= region.start && time <= region.end);
  }

  /**
   * 次の音声リージョンを選択
   * @param {boolean} reversed - 逆方向に選択するかどうか
   * @returns {WaveSurfer.Region|null} - 選択された音声リージョン
   */
  selectNextAudioRegion(reversed = false) {
    const regionsPlugin = this.getRegionsPlugin();

    // すべてのリージョンを取得
    const regions = regionsPlugin.regions;

    if (regions.length === 0) {
      console.warn("No regions available.");
      return;
    }

    // 現在選択中のリージョンのインデックスを取得
    const currentIndex = regions.findIndex((region) => region === this.state.selectedRegion);
    let nextIndex = -1;

    // 選択中のリージョンがない場合は現在の再生位置に最も近いリージョンを選択
    if (currentIndex === -1) {
      const currentTime = this.waveSurfer.getCurrentTime();
      const distances = regions.map((region) => {
        const distance = reversed ? -(region.end - currentTime) : region.start - currentTime;
        return distance < 0 ? Number.MAX_VALUE : distance;
      });
      nextIndex = distances.indexOf(Math.min(...distances));
      // nextIndex = reversed ? regions.length - 1 : 0;
    } else {
      // 次または前のインデックスを計算
      if (reversed) {
        // 逆方向（循環）
        nextIndex = (currentIndex - 1 + regions.length) % regions.length;
      } else {
        // 順方向（循環）
        nextIndex = (currentIndex + 1) % regions.length;
      }
    }

    // 選択されたリージョンを更新
    this.state.selectedRegion = regions[nextIndex];
  }

  /**
   * アノテーションを保存する
   * @param {WaveSurfer.Region} region - 保存するアノテーションのリージョン
   */
  async saveAnnotation(region) {
    // アノテーションが変更されていない場合は何もしない
    if (!region.annotation["isChanged"]) {
      delete region.annotation["isChanged"];
      return;
    }
    delete region.annotation["isChanged"];
    // アノテーションを保存    
    try {
      let payload = JSON.parse(JSON.stringify(region.annotation));
      payload["uid"] = this.imageManager.stats.uid;
      const response = await fetch("/update/annotation", {
        method: "POST", // またはPUT
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });
      if (response.ok) {
        console.log("Annotation saved successfully.");
      } else {
        console.error("Failed to save annotation:", response.statusText);
        throw new Error(`Failed to save annotation: ${response.statusText}`);
      }
    } catch (error) {
      console.error("Error saving annotation:", error);
      throw error;
    }
    // アノテーションを再取得（サーバーと同期）
    await Promise.all([
      this.imageManager.loadImageAnnotation(region.annotation.page_index != null ? region.annotation.page_index : this.imageManager.state.currentPage),
      this.loadVoiceAnnotation(region.annotation.id)
    ]);
    this.selectAudioRegion(region);
  }

  /**
   * アノテーションをリセットする
   * @param {WaveSurfer.Region} region - リセットするアノテーションのリージョン
   */
  async resetAnnotation(region) {
    // アノテーションが変更されていない場合は何もしない
    if (!region.annotation["isChanged"]) {
      delete region.annotation["isChanged"];
      return;
    }
    delete region.annotation["isChanged"];
    // アノテーションをリセット
    await Promise.all([
      this.imageManager.loadImageAnnotation(region.annotation.page_index != null ? region.annotation.page_index : this.imageManager.state.currentPage),
      this.loadVoiceAnnotation(region.annotation.id)
    ]);
    // 対象のリージョンのstartとendを更新
    region.setOptions({ start: region.annotation.start, end: region.annotation.end });
    //
    this.selectAudioRegion(region);
  }

  // /** TODO:
  //  * アノテーションをフィルタリングする
  //  */
  // filterAnnotations() {
  //   // フィルタ関連の要素を取得
  //   const abnormalityFilterCheckbox = document.getElementById("abnormality_filter");
  //   const voiceFilterInput = document.getElementById("voice_filter");
  //   const audioFilterSelect = document.getElementById("audio_id_filter");
  //   const actorFilterSelect = document.getElementById("actor_id_filter");
  //   const characterFilterSelect = document.getElementById("character_id_filter");
  //   const noteFilterCheckbox = document.getElementById("annotation_note_filter");
  //   const commentFilterCheckbox = document.getElementById("annotation_comment_filter");
  //   // フィルタの値を取得
  //   const isAbnormalityOnly = abnormalityFilterCheckbox.checked;
  //   const voiceFilterValue = voiceFilterInput.value.trim();
  //   const audioValue = audioFilterSelect.value;
  //   const actorValue = actorFilterSelect.value;
  //   const characterValue = characterFilterSelect.value;
  //   const hasNoteOnly = noteFilterCheckbox.checked;
  //   const hasCommentOnly = commentFilterCheckbox.checked;
  //   // 正規表現でチェック
  //   let voiceRegex = null;
  //   try {
  //     voiceRegex = new RegExp(voiceFilterValue, "i");
  //   } catch (error) {
  //     console.warn("Invalid regex:", error);
  //     this.activeAnnotationIndices = [];
  //     return;
  //   }
  //   // フィルタリング
  //   if (this.annotations == null) {
  //     console.warn("Annotations are not loaded yet.");
  //     return;
  //   }
  //   this.activeAnnotationIndices = this.annotations.reduce((indices, annotation, index) => {
  //     let matchesAbnormality = true;
  //     let matchesVoice = true;
  //     let matchesAudio = true;
  //     let matchesActor = true;
  //     let matchesCharacter = true;
  //     let matchesNote = true;
  //     let matchesComment = true;
  //     // abnormality filterでのチェック
  //     if (isAbnormalityOnly) {
  //       matchesAbnormality = !this.isVoiceAnnotationNormal(annotation);
  //     }
  //     // voice regexでのチェック
  //     if (voiceFilterValue) {
  //       matchesVoice = voiceRegex.test(annotation.id);
  //     }
  //     // audio filterでのチェック
  //     if (audioValue) {
  //       matchesAudio = annotation.audio_id === audioValue;
  //     }
  //     // actor filterでのチェック
  //     if (actorValue) {
  //       matchesActor = annotation.actor_id === actorValue;
  //     }
  //     // character filterでのチェック
  //     if (characterValue) {
  //       matchesCharacter = annotation.character_id === characterValue;
  //     }
  //     // note filterでのチェック
  //     if (hasNoteOnly) {
  //       matchesNote = annotation.note.text != "";
  //     }
  //     // comment filterでのチェック
  //     if (hasCommentOnly) {
  //       matchesComment = annotation.annotation_comment != null;
  //     }
  //     // 全ての条件を満たすかどうか
  //     if (matchesAbnormality && matchesVoice && matchesAudio && matchesActor && matchesCharacter && matchesNote && matchesComment) {
  //       indices.push(index);
  //     }
  //     return indices;
  //   }, []);
  //   // フィルタされて得られる個数の更新
  //   document.getElementById("annotation_filter_header").textContent = `Filtered annotations: ${this.activeAnnotationIndices.length} / ${this.annotations.length}`;
  //   return;
  // }


  //////////////////////////
  //// Event listeners /////
  //////////////////////////
  setupEventListeners() {
    // waveform
    const waveformContainer = document.getElementById("waveform");
    waveformContainer.addEventListener("wheel", (event) => {
      event.preventDefault();
      if (event.deltaY < 0) {
        this.state.zoomLevel = this.state.zoomLevel + 2; // ズームイン
      } else {
        this.state.zoomLevel = this.state.zoomLevel - 2; // ズームアウト
      }
    });

    // スペースキーの動作
    document.addEventListener("keydown", (event) => {
      if (event.code === "Space") {
        event.preventDefault(); // ページスクロールを防止

        if (this.waveSurfer) {
          if (this.waveSurfer.isPlaying()) {
            this.waveSurfer.pause();
          } else if (this.state.selectedRegion) {
            // 選択されたRegionを再生
            this.waveSurfer.play(this.state.selectedRegion.start, this.state.selectedRegion.end);
          } else {
            this.waveSurfer.play();
          }
        }
      }
      // 次のリージョンを選択
      if (event.code === "KeyN") {
        this.selectNextAudioRegion(false);
      }
      // 前のリージョンを選択
      if (event.code === "KeyB") {
        this.selectNextAudioRegion(true);
      }
      // アノテーションをセーブ
      if (event.code === "KeyS") {
        if (this.state.selectedRegion && !document.getElementById("frame_id").disabled) {
          document.getElementById("saveAnnotation").click();
        } else {
          console.error("This operation is not allowed without selecting a region.");
        }
      }
      // アノテーションをリセット（再取得）
      if (event.code === "KeyR") {
        if (this.state.selectedRegion && !document.getElementById("frame_id").disabled) {
          document.getElementById("resetAnnotation").click();
        } else {
          console.error("This operation is not allowed without selecting a region.");
        }
      }
      // ヘルプを表示
      if (event.code == "KeyH") {
        this.toggleHelp();
      }
    });

    // プルダウンメニューの変更時の動作
    ["actor_id", "text_id", "frame_id", "body_id", "face_id", "character_id"].forEach((elementId) => {
      const redrawImageAnnotation = (event) => {
        if (this.state.selectedRegion) {
          if (elementId == "character_id") {
            // キャラクターIDが変更された場合，キャラクター名も更新
            this.state.selectedRegion.annotation.character_id = event.target.value;
            this.state.selectedRegion.annotation.character_name = this.characters.find((candidate) => candidate.id === event.target.value).name;
            this.writeAnnotationDetails(this.state.selectedRegion.annotation);
          } else if (elementId == "frame_id" || elementId == "face_id" || elementId == "body_id") {
            // 複数選択に対応
            const selectedValues = Array.from(event.target.selectedOptions).map(option => option.value);
            const commaSeparatedValues = selectedValues.join(",");
            this.state.selectedRegion.annotation[elementId] = commaSeparatedValues || null;
          } else {
            this.state.selectedRegion.annotation[elementId] = event.target.value == "null" ? null : event.target.value;
          }
          this.imageManager.drawImageAnnotations([this.state.selectedRegion.annotation]);
          this.state.selectedRegion.annotation["isChanged"] = true;
        } else {
          console.error("This operation is not allowed without selecting a region.");
        }
      };
      document.getElementById(elementId).addEventListener("change", redrawImageAnnotation);
    });

    // フリーフォームテキストの変更時の動作
    ["page_index", "annotation_comment", "spoken_text"].forEach((elementId) => {
      const redrawImageAnnotation = (event) => {
        if (this.state.selectedRegion) {
          if (elementId === "page_index") {
            this.state.selectedRegion.annotation.page_index = parseInt(event.target.value, 10);
          } else if (elementId === "spoken_text") {
            this.state.selectedRegion.annotation.text = event.target.value;
          } else {
            this.state.selectedRegion.annotation[elementId] = { "text": event.target.value };
          }
          this.state.selectedRegion.annotation["isChanged"] = true;
        } else {
          console.error("This operation is not allowed without selecting a region.");
        }
      };
      document.getElementById(elementId).addEventListener("input", redrawImageAnnotation);
    });
    {
      // クリック時に選択されたリージョンの状態をトグル
      ["frame_id", "face_id", "body_id"].forEach((elementId) => {
        const selectElement = document.getElementById(elementId);
        selectElement.addEventListener("mousedown", (event) => {
          if (event.target.tagName == "OPTION") {
            event.preventDefault();
            const option = event.target;
            // 選択状態を反転
            option.selected = !option.selected;
            // changeイベントを発火
            const changeEvent = new Event("change", { bubbles: true });
            selectElement.dispatchEvent(changeEvent);
          }
        });
      });
    }

    // アノテーション編集後にセーブ
    document.getElementById("saveAnnotation").addEventListener("click", async () => {
      if (this.state.selectedRegion) {
        await this.saveAnnotation(this.state.selectedRegion);
      }
    });
    // アノテーションをリセット（再取得）
    document.getElementById("resetAnnotation").addEventListener("click", async () => {
      if (this.state.selectedRegion) {
        await this.resetAnnotation(this.state.selectedRegion);
      }
    });

    // canvas上でマウス移動時にバウンディングボックスを検出
    const canvas = document.getElementById("manga_canvas");
    canvas.addEventListener("mousemove", (event) => {
      if (this.state.selectedRegion && !document.getElementById("frame_id").disabled) {
        const rect = canvas.getBoundingClientRect();
        const x = event.clientX - rect.left;
        const y = event.clientY - rect.top;
        const boundingBox = this.imageManager.getSmallestBoundingBoxFromMouse(x, y);
        if (boundingBox) {
          const targetColor = this.imageManager.styles[boundingBox.annotationType].getStyle(1);
          document.getElementById("image_annotation_details_id").textContent = boundingBox.id;
          document.getElementById("image_annotation_details_type").textContent = boundingBox.annotationType;
          document.getElementById("image_annotation_details").style.color = targetColor;
        } else {
          document.getElementById("image_annotation_details_id").textContent = "";
          document.getElementById("image_annotation_details_type").textContent = "";
          document.getElementById("image_annotation_details").style.color = "black";
        }
      }
    });
    canvas.addEventListener("mouseover", (event) => {
      if (this.state.selectedRegion && !document.getElementById("frame_id").disabled) {
        document.getElementById("image_annotation_details_id").textContent = "";
        document.getElementById("image_annotation_details_type").textContent = "";
        document.getElementById("image_annotation_details").style.color = "black";
      }
    });
    canvas.addEventListener("mouseleave", (event) => {
      if (this.state.selectedRegion && !document.getElementById("frame_id").disabled) {
        document.getElementById("image_annotation_details_id").textContent = "";
        document.getElementById("image_annotation_details_type").textContent = "";
        document.getElementById("image_annotation_details").style.color = "black";
      }
    });
    // canvas上でクリックすると当該アノテーションを選択
    canvas.addEventListener("click", (event) => {
      if (this.state.selectedRegion && !document.getElementById("frame_id").disabled) {
        const rect = canvas.getBoundingClientRect();
        const x = event.clientX - rect.left;
        const y = event.clientY - rect.top;
        const boundingBox = this.imageManager.getSmallestBoundingBoxFromMouse(x, y);
        if (boundingBox) {
          let voiceKey = null;
          if (boundingBox.annotationType === "texts") {
            voiceKey = "text_id";
          } else if (boundingBox.annotationType === "frames") {
            voiceKey = "frame_id";
          } else if (boundingBox.annotationType === "bodies") {
            voiceKey = "body_id";
          } else if (boundingBox.annotationType === "faces") {
            voiceKey = "face_id";
          } else {
            console.error("Invalid annotation type.");
          }
          // プルダウンメニューを更新
          if (voiceKey === "frame_id" || voiceKey === "face_id" || voiceKey === "body_id") {
            const selectElement = document.getElementById(voiceKey);
            const selectedValues = Array.from(selectElement.selectedOptions).map(option => option.value);

            // 選択されている値に現在クリックされた boundingBox.id を追加または削除
            const index = selectedValues.indexOf(boundingBox.id);
            if (index === -1) {
              // 新しい値を追加
              selectedValues.push(boundingBox.id);
            } else {
              // 既存の値を削除
              selectedValues.splice(index, 1);
            }

            // 更新された選択を反映
            Array.from(selectElement.options).forEach(option => {
              option.selected = selectedValues.includes(option.value);
            });
          } else {
            const contentSelect = document.getElementById(voiceKey);
            if (contentSelect.value != boundingBox.id) {
              contentSelect.value = boundingBox.id;
            } else {
              contentSelect.value = null;
            }
          }
          // マニュアルでchangeイベントを発火
          const changeEvent = new Event("change");
          document.getElementById(voiceKey).dispatchEvent(changeEvent);
        }
      }
    });

    const commentTextarea = document.getElementById('annotation_comment');
    commentTextarea.addEventListener('keydown', (event) => {
      event.stopPropagation(); // 親要素への伝播を防ぐ
    });

    // ウィンドウリサイズ時にキャンバスサイズを更新
    window.addEventListener("resize", () => {
      this.imageManager.updateCanvasSize();
      const targetAnnotations = [];
      for (const region of this.state.activeRegions) {
        targetAnnotations.push(region.annotation);
      }
      if (this.state.selectedRegion) {
        targetAnnotations.push(this.state.selectedRegion.annotation);
      }
      this.imageManager.drawImageAnnotations(targetAnnotations);
    });

    {
      const voiceEditModeToggle = document.getElementById("voice_edit_mode_toggle");
      voiceEditModeToggle.addEventListener("change", () => {
        this.toggleVoiceEditability();
      });
    }
  }
}

// Initialize the tool
document.addEventListener("DOMContentLoaded", () => {
  const tool = new MangaAnnotationTool();
  tool
    .initialize()
    .then(() => {
      console.log("Tool initialized successfully.");
    })
    .catch((error) => {
      console.error("Error initializing tool:", error);
    });
});

