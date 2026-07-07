
const HELP_DESCRIPTION = `
  <h5>Help: Keyboard Shortcuts</h5>
  <ul>
    <li><strong>Space:</strong> Play/Pause audio</li>
    <li><strong>Press n:</strong> Select next voice</li>
    <li><strong>Press b:</strong> Select previous voice</li>
    <li><strong>Press s:</strong> Save the selected voice</li>
    <li><strong>Press r:</strong> Reset the selected voice</li>
    <li><strong>Click the canvas:</strong> Select the image annotation containing the coordinate position of the mouse when a voice is selected. If the position is included in multiple annotations, the minimum-area annotation is selected.</li>
    <li><strong>Press h:</strong> Show/hide this help message</li>
  </ul>
  <p>Select a voice by using the keyboard shortcuts or clicking directly on the waveform.</p>
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

  /**
   * コンストラクタ
   * シングルトンパターンを使用して、インスタンスを一つだけにする
   */
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
        currentVoiceIndex: -1, // 現在の音声アノテーションのインデックス
        isLoading: false, // ロード中かどうかのフラグ
      },
      {
        set: (target, key, value) => {
          if (key == "currentVoiceIndex") {
            // 現在の音声アノテーションのインデックス変更時
            // 範囲外になったらループ
            while (value < 0) {
              value += this.annotations.length;
            }
            value = value % this.annotations.length;
            // ロード中の場合は警告を出して何もしない
            if (target.isLoading) {
              console.warn("Loading is in progress.");
              return true;
            }
            this.state.isLoading = true;
            // 現在のアノテーションを保存
            this.setEditElementsEnabled(false);
            this.saveAnnotation(this.annotations[target[key]]).then(() => {
              target[key] = value;
              // 編集要素を無効化
              this.setEditElementsEnabled(false);
              // オーディオデータを読み直し
              this.loadAudio(this.annotations[value].id).then(() => {
                this.loadVoiceAndImageAnnotationsAfterAudioLoaded(value);
              }).catch((error) => {
                console.error("Error loading audio:", error);
              }).finally(() => {
                this.state.isLoading = false;
              });
            }).catch((error) => {
              console.error("Error saving annotation:", error);
              this.state.isLoading = false;
            });
          } else if (key == "isLoading") {
            // ロード中フラグの変更時
            if (value) {
              document.body.style.cursor = "wait";
            } else {
              document.body.style.cursor = "default";
            }
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
    this.waveSurferInstances = [];
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
      // 画像読み込み，アノテーション読み込み，オーディオ読み込み
      await Promise.all([this.imageManager.initialize(), this.loadVoiceAnnotation(), this.loadCharacters(), this.loadAudioCharacters(), this.loadActors()]);
    } catch (error) {
      this.setOverlayState(true, error.message); // エラーメッセージを表示
    }
    // フィルターを初期化
    this.initializeFilter();
    // イベントリスナーを設定
    this.setupEventListeners();
    this.imageManager.setupEventListeners();
    // 画像上にアノテーションを描画
    this.imageManager.drawImageAnnotations([]);
    // 編集要素を無効化
    this.setEditElementsEnabled(false);
    // オーディオ読み込み完了後にオーバーレイを非表示
    this.setOverlayState(false, "");
    // 最初のアノテーションを選択
    this.state.currentVoiceIndex = 0;
  }

  /**
   * フィルタ処理を行うための初期化
   */
  initializeFilter() {
    // フィルタ関連の要素を取得
    const abnormalityFilterCheckbox = document.getElementById("abnormality_filter");
    const voiceFilterInput = document.getElementById("voice_filter");
    const audioFilterSelect = document.getElementById("audio_id_filter");
    const actorFilterSelect = document.getElementById("actor_id_filter");
    const characterFilterSelect = document.getElementById("character_id_filter");
    const spokenTextFilterCheckbox = document.getElementById("spoken_text_filter");
    const noteFilterCheckbox = document.getElementById("annotation_note_filter");
    const commentFilterCheckbox = document.getElementById("annotation_comment_filter");
    // audio IDフィルター用に音声キャラクターを設定
    audioFilterSelect.innerHTML = '<option value="">All</option>';
    this.audioCharacters.forEach((audioCharacter) => {
      const option = document.createElement("option");
      option.value = audioCharacter;
      option.text = audioCharacter;
      audioFilterSelect.appendChild(option);
    });
    // actor IDフィルター用に俳優を設定
    actorFilterSelect.innerHTML = '<option value="">All</option>';
    this.actors.forEach((actor) => {
      const option = document.createElement("option");
      option.value = actor;
      option.text = actor;
      actorFilterSelect.appendChild(option);
    });
    // character IDフィルター用にキャラクターを設定
    characterFilterSelect.innerHTML = '<option value="">All</option>';
    this.characters.forEach((character) => {
      const option = document.createElement("option");
      option.value = character.id;
      option.text = character.name;
      characterFilterSelect.appendChild(option);
    });
    // イベントリスナーを設定
    [abnormalityFilterCheckbox, voiceFilterInput, audioFilterSelect, actorFilterSelect, characterFilterSelect, spokenTextFilterCheckbox, noteFilterCheckbox, commentFilterCheckbox].forEach((input) => {
      input.addEventListener("input", () => { this.filterAnnotations(); });
    });
    // 初期状態では全てのアノテーションを表示
    this.activeAnnotationIndices = this.annotations.map((annotation, index) => index);
  }

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
   * 音声と画像のアノテーションを読み込む
   * @param {number} value 
   */
  loadVoiceAndImageAnnotationsAfterAudioLoaded(value) {
    // 編集要素を無効化
    this.setEditElementsEnabled(false);
    // 画像にアノテーション描画
    this.imageManager.drawImageAnnotations([this.annotations[value]]);
    // アノテーションの番号を表示
    document.getElementById("annotation_details_head").innerHTML = `Annotation Details: ${value + 1} / ${this.annotations.length} (${this.activeAnnotationIndices.indexOf(value) + 1}/${this.activeAnnotationIndices.length} filtered)`;
    document.getElementById("annotation_details_head").style.backgroundColor = this.isVoiceAnnotationNormal(this.annotations[value]) ? "" : this.styles.toBeFixed;
    // アノテーションの詳細を表示
    this.writeAnnotationDetails(this.annotations[value]);
    // 編集要素を有効化
    this.setEditElementsEnabled(true);
  }

  /**
   * 音声を読み込む
   * @param {string} voiceId 
   * @returns 
   */
  async loadAudio(voiceId) {
    // wavesurfer instanceを破棄
    if (this.waveSurferInstances.length > 0) {
      this.waveSurferInstances.forEach((waveSurfer) => {
        waveSurfer.destroy();
      });
      const waveformContainer = document.getElementById("waveform_container");
      waveformContainer.innerHTML = "";
      this.waveSurferInstances = [];
      this.activeAudioCharacters = [];
    }

    if (voiceId == null) {
      // voiceIdが指定されていない場合は何もしない
      console.warn("No voice ID specified. Skipping audio load.");
      return;
    }

    // 音声のロードを非同期で処理
    await this.loadAudioCharacters(voiceId);
    for (const audioCharacter of this.activeAudioCharacters) {
      const waveSurfer = this.initializeWaveSurfer(audioCharacter);
      await waveSurfer.load(`/audio/${audioCharacter}/${voiceId}`);
      this.waveSurferInstances.push(waveSurfer);
    }
  }

  /**
   * wavesurferを初期化する
   * @param {string} audioCharacter 
   * @returns {WaveSurfer}
   */
  initializeWaveSurfer(audioCharacter) {
    // ラベルと波形の行を作成
    const waveformRow = document.createElement("div");
    waveformRow.classList.add("waveform_row");

    // ラベルを作成
    const label = document.createElement("div");
    label.classList.add("waveform_label");
    label.textContent = audioCharacter;

    // 波形のコンテナを作成
    const waveSurferContainer = document.createElement("div");
    waveSurferContainer.classList.add("waveform_container");
    waveSurferContainer.id = `waveform_${audioCharacter}`;

    // 行にラベルと波形を追加
    waveformRow.appendChild(label);
    waveformRow.appendChild(waveSurferContainer);
    document.getElementById("waveform_container").appendChild(waveformRow);

    // WaveSurferのインスタンスを作成
    const waveSurfer = WaveSurfer.create({
      container: `#waveform_${audioCharacter}`,
      waveColor: "#6c757d",
      progressColor: "#0d6efd",
      cursorColor: "#dc3545",
      barWidth: 3,
      height: 64,
      pixelRatio: 1,
      responsive: true,
      normalize: true,
      backend: "MediaElement",
      partialRender: true,
      scrollParent: true,
      mediaControls: false,
      plugins: [WaveSurfer.Regions.create()],
    });

    // 対象区間にリージョンを設定
    waveSurfer.on("ready", () => {
      const regionsPlugin = waveSurfer.getActivePlugins().find(
        (plugin) => plugin instanceof WaveSurfer.Regions
      );
      regionsPlugin.addRegion({
        start: 0.5, // 開始位置はmain2.pyで指定済み (500 ms)
        end: waveSurfer.getDuration() - 0.5, // 終了位置はmain2.pyで指定済み (500 ms)
        color: this.styles.normal,
        drag: false,
        resize: false
      });
    });

    // 再生している間は編集を無効化
    waveSurfer.on("play", () => {
      this.setEditElementsEnabled(false);
    });
    waveSurfer.on("pause", () => {
      this.setEditElementsEnabled(true);
    });
    waveSurfer.on("finish", () => {
      this.setEditElementsEnabled(true);
    });
    return waveSurfer;
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
    ["actor_id", "spoken_text", "audio_id", "text_id", "page_index", "frame_id", "body_id", "face_id", "character_id", "annotation_comment"].forEach((elementId) => {
      document.getElementById(elementId).disabled = !enabled;
    });
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

  async deleteAnnotation(annotation) {
    // アノテーションがnullの場合は何もしない
    if (annotation == null) {
      return;
    }
    // アノテーションを削除
    try {
      const response = await fetch(`/delete/annotation/${annotation.id}`);
      if (response.ok) {
        console.log("Annotation deleted successfully.");
      } else {
        console.error("Failed to delete annotation:", response.statusText);
        throw new Error(`Failed to delete annotation: ${response.statusText}`);
      }
    } catch (error) {
      console.error("Error deleting annotation:", error);
      throw error;
    }
    // アノテーション全体を再取得（サーバーと同期）
    const previousAnnotationIndex = this.annotations.findIndex((candidate) => candidate.id === annotation.id);
    await Promise.all([
      this.imageManager.loadImageAnnotation(annotation.page_index != null ? annotation.page_index : this.imageManager.state.currentPage),
      this.loadVoiceAnnotation()
    ]);
    // filterを再適用
    this.filterAnnotations();
    // 次のアノテーションを選択
    const newAnnotationIndex = Math.min(previousAnnotationIndex, this.annotations.length - 1);
    await this.loadAudio(this.annotations[newAnnotationIndex].id);
    this.loadVoiceAndImageAnnotationsAfterAudioLoaded(newAnnotationIndex);
  }

  /**
   * アノテーションを保存する
   * @param {Object} annotation - 保存するアノテーションオブジェクト
   * @returns {Promise<void>}
   */
  async saveAnnotation(annotation) {
    // アノテーションがnullの場合は何もしない
    if (annotation == null) {
      return;
    }
    // アノテーションが変更されていない場合は何もしない
    if (!annotation["isChanged"]) {
      delete annotation["isChanged"];
      return;
    }
    delete annotation["isChanged"];
    // アノテーションを保存    
    try {
      let payload = JSON.parse(JSON.stringify(annotation));
      payload["uid"] = this.imageManager.stats.uid;
      const response = await fetch("/update/annotation", {
        method: "POST",
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
      this.imageManager.loadImageAnnotation(annotation.page_index != null ? annotation.page_index : this.imageManager.state.currentPage),
      this.loadVoiceAnnotation(annotation.id)
    ]);
    const value = this.annotations.findIndex((candidate) => candidate.id === annotation.id);
    this.loadVoiceAndImageAnnotationsAfterAudioLoaded(value);
  }

  /**
   * アノテーションをリセットする
   * @param {Object} annotation - リセットするアノテーションオブジェクト
   * @returns {Promise<void>}
   */
  async resetAnnotation(annotation) {
    // アノテーションがnullの場合は何もしない
    if (!annotation["isChanged"]) {
      delete annotation["isChanged"];
      return;
    }
    delete annotation["isChanged"];
    // アノテーションをリセット
    await Promise.all([
      this.imageManager.loadImageAnnotation(annotation.page_index != null ? annotation.page_index : this.imageManager.state.currentPage),
      this.loadVoiceAnnotation(annotation.id)
    ]);
  }

  /**
   * アノテーションをフィルタリングする
   */
  filterAnnotations() {
    // フィルタ関連の要素を取得
    const abnormalityFilterCheckbox = document.getElementById("abnormality_filter");
    const voiceFilterInput = document.getElementById("voice_filter");
    const audioFilterSelect = document.getElementById("audio_id_filter");
    const actorFilterSelect = document.getElementById("actor_id_filter");
    const characterFilterSelect = document.getElementById("character_id_filter");
    const spokenTextFilterCheckbox = document.getElementById("spoken_text_filter");
    const noteFilterCheckbox = document.getElementById("annotation_note_filter");
    const commentFilterCheckbox = document.getElementById("annotation_comment_filter");
    // フィルタの値を取得
    const isAbnormalityOnly = abnormalityFilterCheckbox.checked;
    const voiceFilterValue = voiceFilterInput.value.trim();
    const audioValue = audioFilterSelect.value;
    const actorValue = actorFilterSelect.value;
    const characterValue = characterFilterSelect.value;
    const hasNoSpokenTextOnly = spokenTextFilterCheckbox.checked;
    const hasNoteOnly = noteFilterCheckbox.checked;
    const hasCommentOnly = commentFilterCheckbox.checked;
    // 正規表現でチェック
    let voiceRegex = null;
    try {
      voiceRegex = new RegExp(voiceFilterValue, "i");
    } catch (error) {
      console.warn("Invalid regex:", error);
      this.activeAnnotationIndices = [];
      return;
    }
    // フィルタリング
    if (this.annotations == null) {
      console.warn("Annotations are not loaded yet.");
      return;
    }
    this.activeAnnotationIndices = this.annotations.reduce((indices, annotation, index) => {
      let matchesAbnormality = true;
      let matchesVoice = true;
      let matchesAudio = true;
      let matchesActor = true;
      let matchesCharacter = true;
      let matchesNote = true;
      let matchesComment = true;
      // abnormality filterでのチェック
      if (isAbnormalityOnly) {
        matchesAbnormality = !this.isVoiceAnnotationNormal(annotation);
      }
      // voice regexでのチェック
      if (voiceFilterValue) {
        matchesVoice = voiceRegex.test(annotation.id);
      }
      // audio filterでのチェック
      if (audioValue) {
        matchesAudio = annotation.audio_id === audioValue;
      }
      // actor filterでのチェック
      if (actorValue) {
        matchesActor = annotation.actor_id === actorValue;
      }
      // character filterでのチェック
      if (characterValue) {
        matchesCharacter = annotation.character_id === characterValue;
      }
      // spoken text filterでのチェック
      if (hasNoSpokenTextOnly) {
        matchesVoice = annotation.text.trim() === "";
      }
      // note filterでのチェック
      if (hasNoteOnly) {
        matchesNote = annotation.note.text != "";
      }
      // comment filterでのチェック
      if (hasCommentOnly) {
        matchesComment = annotation.annotation_comment != null;
      }
      // 全ての条件を満たすかどうか
      if (matchesAbnormality && matchesVoice && matchesAudio && matchesActor && matchesCharacter && matchesNote && matchesComment) {
        indices.push(index);
      }
      return indices;
    }, []);
    // フィルタされて得られる個数の更新
    document.getElementById("annotation_filter_header").textContent = `Filtered annotations: ${this.activeAnnotationIndices.length} / ${this.annotations.length}`;
    return;
  }

  /**
   * イベントリスナーを設定
   */
  setupEventListeners() {
    document.addEventListener("keydown", (event) => {
      // スペースキーの動作
      if (event.code === "Space") {
        event.preventDefault(); // ページスクロールを防止
        if (this.waveSurferInstances.length > 0) {
          const isPlaying = this.waveSurferInstances.map((waveSurfer) => waveSurfer.isPlaying()).reduce((a, b) => a || b);
          if (isPlaying) {
            this.waveSurferInstances.forEach((waveSurfer) => waveSurfer.pause());
          } else {
            if (this.annotations[this.state.currentVoiceIndex].audio_id) {
              // audio_idが指定されていれば，その音声のみ再生
              const selectedAudioCharacter = this.annotations[this.state.currentVoiceIndex].audio_id;
              const selectedAudioCharacterIndex = this.activeAudioCharacters.findIndex((candidate) => candidate === selectedAudioCharacter);
              this.waveSurferInstances[selectedAudioCharacterIndex].play();
            } else {
              // audio_idが指定されてなければ，全ての音声を再生
              this.waveSurferInstances.forEach((waveSurfer) => waveSurfer.play());
            }
          }
        }
      }
      // 次の音声アノテーションを選択
      if (event.code === "KeyN") {
        // 次の音声アノテーションを選択
        if (this.annotations.length !== this.activeAnnotationIndices.length) {
          // アクティブなアノテーションが全てのアノテーションでない場合
          // this.state.currentVoiceIndexよりも大きくかつ，this.activeAnnotationIndicesの中で最小のインデックスを取得
          const nextIndex = this.activeAnnotationIndices.filter((index) => index > this.state.currentVoiceIndex).reduce((a, b) => Math.min(a, b), Infinity);
          // 次の音声アノテーションがない場合は最初の音声アノテーションを選択
          this.state.currentVoiceIndex = nextIndex !== Infinity ? nextIndex : this.activeAnnotationIndices[0];
        } else {
          this.state.currentVoiceIndex = this.state.currentVoiceIndex + 1;
        }
      }
      // 前の音声アノテーションを選択
      if (event.code === "KeyB") {
        if (this.annotations.length !== this.activeAnnotationIndices.length) {
          // アクティブなアノテーションが全てのアノテーションでない場合
          // this.state.currentVoiceIndexよりも小さくかつ，this.activeAnnotationIndicesの中で最大のインデックスを取得
          const prevIndex = this.activeAnnotationIndices.filter((index) => index < this.state.currentVoiceIndex).reduce((a, b) => Math.max(a, b), -Infinity);
          // 前の音声アノテーションがない場合は最後の音声アノテーションを選択
          this.state.currentVoiceIndex = prevIndex !== -Infinity ? prevIndex : this.activeAnnotationIndices[this.activeAnnotationIndices.length - 1];
        } else {
          // 前の音声アノテーションを選択
          this.state.currentVoiceIndex = this.state.currentVoiceIndex - 1;
        }
      }
      // アノテーションをセーブ
      if (event.code === "KeyS") {
        if (!document.getElementById("frame_id").disabled) {
          document.getElementById("saveAnnotation").click();
        } else {
          console.error("This operation is not allowed.");
        }
      }
      // アノテーションをリセット（再取得）
      if (event.code === "KeyR") {
        if (!document.getElementById("frame_id").disabled) {
          document.getElementById("resetAnnotation").click();
        } else {
          console.error("This operation is not allowed.");
        }
      }
      // ヘルプを表示
      if (event.code == "KeyH") {
        this.toggleHelp();
      }
    });

    // プルダウンメニューの変更時の動作
    ["actor_id", "audio_id", "text_id", "frame_id", "body_id", "face_id", "character_id"].forEach((elementId) => {
      const redrawImageAnnotation = (event) => {
        if (elementId == "character_id") {
          // キャラクターIDが変更された場合、キャラクター名も更新
          this.annotations[this.state.currentVoiceIndex].character_id = event.target.value;
          this.annotations[this.state.currentVoiceIndex].character_name = this.characters.find((candidate) => candidate.id === event.target.value).name;
          this.writeAnnotationDetails(this.annotations[this.state.currentVoiceIndex]);
        } else if (elementId == "frame_id" || elementId == "face_id" || elementId == "body_id") {
          // 複数選択に対応
          const selectedValues = Array.from(event.target.selectedOptions).map(option => option.value);
          const commaSeparatedValues = selectedValues.join(",");
          this.annotations[this.state.currentVoiceIndex][elementId] = commaSeparatedValues || null;
        } else {
          this.annotations[this.state.currentVoiceIndex][elementId] = event.target.value == "null" ? null : event.target.value;
        }
        this.imageManager.drawImageAnnotations([this.annotations[this.state.currentVoiceIndex]]);
        this.annotations[this.state.currentVoiceIndex]["isChanged"] = true;
      };
      document.getElementById(elementId).addEventListener("change", redrawImageAnnotation);
    });

    // フリーフォームテキストの変更時の動作
    ["page_index", "annotation_comment", "spoken_text"].forEach((elementId) => {
      const redrawImageAnnotation = (event) => {
        if (elementId === "page_index") {
          this.annotations[this.state.currentVoiceIndex].page_index = parseInt(event.target.value, 10);
        } else if (elementId === "spoken_text") {
          this.annotations[this.state.currentVoiceIndex].text = event.target.value;
        } else {
          this.annotations[this.state.currentVoiceIndex].annotation_comment = { "text": event.target.value };
        }
        this.annotations[this.state.currentVoiceIndex].isChanged = true;
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
      await this.saveAnnotation(this.annotations[this.state.currentVoiceIndex]);
    });
    // アノテーションをリセット（再取得）
    document.getElementById("resetAnnotation").addEventListener("click", async () => {
      await this.resetAnnotation(this.annotations[this.state.currentVoiceIndex]);
    });
    // アノテーションを削除
    document.getElementById("deleteAnnotation").addEventListener("click", async () => {
      // const confirmation = confirm("Are you sure you want to delete this annotation?");
      // if (confirmation) {
      await this.deleteAnnotation(this.annotations[this.state.currentVoiceIndex]);
      // }
    });

    // canvas上でマウス移動時にバウンディングボックスを検出
    const canvas = document.getElementById("manga_canvas");
    canvas.addEventListener("mousemove", (event) => {
      if (!document.getElementById("frame_id").disabled) {
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
      if (!document.getElementById("frame_id").disabled) {
        document.getElementById("image_annotation_details_id").textContent = "";
        document.getElementById("image_annotation_details_type").textContent = "";
        document.getElementById("image_annotation_details").style.color = "black";
      }
    });
    canvas.addEventListener("mouseleave", (event) => {
      if (!document.getElementById("frame_id").disabled) {
        document.getElementById("image_annotation_details_id").textContent = "";
        document.getElementById("image_annotation_details_type").textContent = "";
        document.getElementById("image_annotation_details").style.color = "black";
      }
    });
    // canvas上でクリックすると当該アノテーションを選択
    canvas.addEventListener("click", (event) => {
      if (!document.getElementById("frame_id").disabled) {
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
      this.imageManager.drawImageAnnotations([this.annotations[this.state.currentVoiceIndex]]);
    });
  }
}

/**
 * メインの処理
 */
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

