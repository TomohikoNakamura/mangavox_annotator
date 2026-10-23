/* Copyright (C) 2025 National Institute of Advanced Industrial Science and Technology (AIST) */


/** Bootstrap Toastを作成する関数
 * @param {string} message - トーストに表示するメッセージ
 * @param {string} type - トーストの種類（"info", "success", "warning", "danger"）
 */
function createToast(message, type = "info") {
  // トーストのHTMLテンプレートを作成
  const toastHTML = `
    <div class="toast align-items-center text-bg-${type} border-0" role="alert" aria-live="assertive" aria-atomic="true">
      <div class="d-flex">
        <div class="toast-body">
          ${message}
        </div>
        <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
      </div>
    </div>
  `;

  // トーストを追加する
  const container = document.getElementById("toast_container");
  container.insertAdjacentHTML("beforeend", toastHTML);

  // トーストを表示する
  const toastElement = container.lastElementChild;
  const toast = new bootstrap.Toast(toastElement);
  toast.show();

  // トーストが終了したら自動的に削除
  toastElement.addEventListener("hidden.bs.toast", () => {
    toastElement.remove();
  });
}

// 元のconsole.logとconsole.errorを保存
const originalLog = console.log;
const originalError = console.error;
const originalWarn = console.warn;

// console.logをラップ
console.log = function (...args) {
  originalLog.apply(console, args);
  createToast(args.join(" "), "info");
};

// console.errorをラップ
console.error = function (...args) {
  originalError.apply(console, args);
  createToast(args.join(" "), "danger");
};

// console.warnをラップ
console.warn = function (...args) {
  originalWarn.apply(console, args);
  createToast(args.join(" "), "warning");
};


/** 画像上のアノテーションの色を定義するクラス
 */
class AnnotationColorStyle {
  /**
   * コンストラクタ
   * @param {Array} baseColor - RGB形式の基本色（例: [255, 0, 0]）
   * @param {Array} alphas - アルファ値の配列（例: [0.5, 1.0]）
   */
  constructor(baseColor, alphas) {
    this.baseColor = baseColor;
    this.alphas = alphas;
  }

  /**
   * 指定されたインデックスに基づいて色を取得
   * @param {number} index - アルファ値のインデックス
   * @returns {string} - RGBA形式の色文字列
   */
  getStyle(index) {
    const [r, g, b] = this.baseColor;
    return `rgba(${r}, ${g}, ${b}, ${this.alphas[index]})`;
  }
}

/** 
 * 画像管理クラス
 */
class ImageManager {
  /**
   * コンストラクタ
   */
  constructor() {
    // 画像上のアノテーション
    this.imageAnnotations = [];
    // ターゲットアノテーション
    this.latestTargetAnnotations = [];
    // 状態の生値
    this._rawState = {
      currentPage: 0,
    }
    // 状態のプロキシ
    this.stats = null;
    this.state = new Proxy(
      this._rawState,
      {
        set: (target, key, value) => {
          // ページ番号の変更時の処理
          if (key === "currentPage" && target[key] !== value && value != null) {
            if (value < this.stats["start_page"] || value > this.stats["end_page"]) {
              return false;
            }
            target[key] = value;
            this.processWithPageChange();
          }
          return true;
        }
      }
    );
    // 画像上のアノテーションのスタイル
    this.styles = {
      texts: new AnnotationColorStyle([0, 123, 255], [0.5, 1.0]), // 青
      frames: new AnnotationColorStyle([40, 167, 69], [0.5, 1.0]), // 緑
      bodies: new AnnotationColorStyle([255, 193, 7], [0.5, 1.0]), // 黄
      faces: new AnnotationColorStyle([220, 53, 69], [0.5, 1.0]), // 赤
    };
  }

  /**
   * 初期化処理
   */
  async initialize() {
    try {
      // アノテーションの読み込み
      await this.loadImageAnnotation();
      // 画像とページ数などの読み込み
      await Promise.all([this.loadImage(), this.loadStats()]);
      // styleに合わせてframe, body, face, textのstrong文字を色付け
      document.getElementById("frame_label").style.color = this.styles.frames.getStyle(1);
      document.getElementById("body_label").style.color = this.styles.bodies.getStyle(1);
      document.getElementById("face_label").style.color = this.styles.faces.getStyle(1);
      document.getElementById("text_label").style.color = this.styles.texts.getStyle(1);
    } catch (error) {
      console.error("Error initializing ImageManager:", error);
      throw error;
    }
  }

  /** 
   * 画像の読み込み
   * @param {Function} onload_func - 画像の読み込み完了後に実行する関数
   * @return {Promise<void>}
   * */
  async loadImage(onload_func = null) {
    try {
      // 画像を取得
      const response = await fetch(`/image/${this.state.currentPage}`);
      if (!response.ok) {
        throw new Error(`Failed to fetch audio: ${response.statusText}`);
      }
      const blob = await response.blob();
      const imageUrl = URL.createObjectURL(blob);

      // 画像要素を取得して設定
      const imageElement = document.getElementById("manga_image");
      if (imageElement) {
        imageElement.onload = () => {
          this.updateCanvasSize();
          if (onload_func) {
            onload_func();
          } else {
            this._drawImageAnnotations([]);
          }
        };
        imageElement.onerror = () => {
          console.error("Error loading image:", imageUrl);
          throw new Error("Error loading image");
        };
        imageElement.src = imageUrl;
      }
    } catch (error) {
      console.error("Error loading image:", error);
      throw error;
    }
  }

  /**
   * 画像のアノテーションを読み込む
   * @param {number} pageNumber - ページ番号
   */
  async loadImageAnnotation(pageNumber = -1) {
    try {
      // 当該画像（ページ）内の画像に対するアノテーションを全部取得
      const response = await fetch(`/annotations/image/${pageNumber}`);
      if (!response.ok) {
        throw new Error(`Failed to fetch annotations: ${response.statusText}`);
      }
      const data = await response.json();
      if (pageNumber < 0) {
        this.imageAnnotations = data;
      } else {
        this.imageAnnotations[pageNumber] = data;
      }
    } catch (error) {
      console.error("Error loading annotations:", error);
      throw error;
    }
  }

  /**
   * ページの統計情報を読み込む
   * @return {Promise<void>}
   */
  async loadStats() {
    try {
      // 統計情報を取得
      const response = await fetch(`/stats`);
      if (!response.ok) {
        throw new Error(`Failed to fetch stats: ${response.statusText}`);
      }
      const data = await response.json();
      this.stats = data;
      // 統計情報をHTMLに反映
      document.getElementById("manga_title").textContent = data["title"];
      document.getElementById("total_pages").textContent = data["total_pages"];
      document.getElementById("current_page_input").min = data["start_page"];
      document.getElementById("current_page_input").max = data["end_page"];
      document.getElementById("page_index").min = data["start_page"];
      document.getElementById("page_index").max = data["end_page"];
    } catch (error) {
      console.error("Error loading stats:", error);
      throw error;
    }
  }

  /**
   * ページ変更時の処理
   * ページが変わった場合に，画像の読み込みとアノテーションの描画を行う
   * @param {Function} onload - 画像の読み込み完了後に実行する関数
   */
  processWithPageChange(onload = null) {
    // 画像をロード
    this.loadImage(onload);
    // ページ番号を更新
    document.getElementById("current_page_input").value = this.state.currentPage;
  }

  /**
   * 画像のアノテーションを描画するラッパー関数
   * ページ数が変わる場合にも対応．
   * @param {Array} targetAnnotations - 描画するアノテーションの配列
   */
  drawImageAnnotations(targetAnnotations = []) {
    this.latestTargetAnnotations = targetAnnotations;
    if (targetAnnotations.length > 0) {
      const targetPageIndex = targetAnnotations[0].page_index;
      if (targetPageIndex != null && this.state.currentPage !== targetPageIndex) {
        // ページが変わる場合は，画像をロードしてアノテーションを描画．onloadで描画．
        this._rawState.currentPage = targetPageIndex;
        this.processWithPageChange(() => {
          this._drawImageAnnotations(targetAnnotations);
        });
        return;
      }
    }
    this._drawImageAnnotations(targetAnnotations);
  }

  /**
   * 画像のアノテーションを描画
   * @param {Array} targetAnnotations - 描画するアノテーションの配列
   */
  _drawImageAnnotations(targetAnnotations) {
    const canvas = document.getElementById("manga_canvas");
    const ctx = canvas.getContext("2d");

    if (!ctx) {
      console.error("Failed to get 2D context from canvas.");
      return;
    }

    // キャンバスをクリア
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // ターゲットとなるIDの収集
    let targetIDs = {};
    [["texts", "text_id"], ["frames", "frame_id"], ["bodies", "body_id"], ["faces", "face_id"]].forEach(([imageKey, voiceKey]) => {
      targetIDs[imageKey] = [];
      for (const targetAnnotation of targetAnnotations) {
        if (voiceKey == "frame_id" || voiceKey == "face_id" || voiceKey == "body_id") {
          // voiceKeyが存在
          if (targetAnnotation[voiceKey]) {
            targetIDs[imageKey].push(...targetAnnotation[voiceKey].split(","));
          }
        } else {
          // テキストの場合は，voiceKeyが存在し，単独IDであることを確認
          if (targetAnnotation[voiceKey] && !targetAnnotation[voiceKey].includes(",")) {
            targetIDs[imageKey].push(...targetAnnotation[voiceKey].split(","));
          }
        }
      }
    });

    // 画像上のアノテーションを描画
    const page = this.imageAnnotations[this.state.currentPage];
    ["texts", "frames", "bodies", "faces"].forEach(imageKey => {
      page[imageKey].forEach((candidate) => {
        // targetAnnotationsに含まれるかどうかを確認
        const styleIndex = targetIDs[imageKey].includes(candidate.id) ? 1 : 0;
        // 色とアルファ値を設定
        const style = this.styles[imageKey];
        ctx.strokeStyle = style.getStyle(styleIndex);
        ctx.lineWidth = 3 * (1 + styleIndex); // 太さは決め打ち
        if (candidate.assigned) {
          ctx.setLineDash([]);
        } else {
          // 現在の発話に対応しない場合は，点線
          ctx.setLineDash([10, 5]);
        }
        // 矩形を描画
        ctx.strokeRect(
          candidate.xmin * this.canvasScaleX,
          candidate.ymin * this.canvasScaleY,
          (candidate.xmax - candidate.xmin) * this.canvasScaleX,
          (candidate.ymax - candidate.ymin) * this.canvasScaleY
        );
      });
    });
  }

  /**
   * 現在のマウス位置を囲む最小の画像上のアノテーションを取得
   * @param {number} キャンバス上のマウスのx座標
   * @param {number} キャンバス上のマウスのy座標
   * @returns {Object|null} - 最小の画像上のアノテーション情報
   */
  getSmallestBoundingBoxFromMouse(x, y) {
    const page = this.imageAnnotations[this.state.currentPage];
    const candidateBoxes = [];
    // x, yを囲むアノテーションを取得し，面積も計算．
    ["texts", "frames", "bodies", "faces"].forEach(imageKey => {
      for (const candidate of page[imageKey]) {
        const scaledBox = {
          xmin: candidate.xmin * this.canvasScaleX,
          xmax: candidate.xmax * this.canvasScaleX,
          ymin: candidate.ymin * this.canvasScaleY,
          ymax: candidate.ymax * this.canvasScaleY,
        };
        if (x >= scaledBox.xmin && x <= scaledBox.xmax && y >= scaledBox.ymin && y <= scaledBox.ymax) {
          candidateBoxes.push({
            annotationType: imageKey,
            id: candidate.id,
            area: (scaledBox.xmax - scaledBox.xmin) * (scaledBox.ymax - scaledBox.ymin),
          });
        }
      }
    });
    // 候補の中から最小の面積を持つアノテーションを選択
    if (candidateBoxes.length > 0) {
      return candidateBoxes.reduce((minBox, box) => minBox.area < box.area ? minBox : box);
    }
    return null;
  }

  /**
   * キャンバスのサイズを更新
   */
  updateCanvasSize() {
    const imageElement = document.getElementById("manga_image");
    const canvas = document.getElementById("manga_canvas");

    if (imageElement && canvas) {
      const displayWidth = imageElement.clientWidth;
      const displayHeight = imageElement.clientHeight;

      canvas.width = displayWidth;
      canvas.height = displayHeight;

      // スケール計算（画像と元データの比率を取得）
      this.canvasScaleX = displayWidth / imageElement.naturalWidth || 1;
      this.canvasScaleY = displayHeight / imageElement.naturalHeight || 1;
    } else {
      console.error("Failed to get image or canvas element.");
    }
  }

  /**
   * イベントリスナーの設定
   */
  setupEventListeners() {
    // ページ変更時のイベントリスナー
    document.getElementById("prevPage").addEventListener("click", () => {
      this.state.currentPage = this.state.currentPage - 1;
    });
    document.getElementById("nextPage").addEventListener("click", () => {
      this.state.currentPage = this.state.currentPage + 1;
    });
    // ページ番号入力のイベントリスナー
    document.getElementById("current_page_input").addEventListener("change", (event) => {
      this.state.currentPage = parseInt(event.target.value, 10);
    });
  }
}
