/* The Markdown editor (design 5.2, v6.70): EasyMDE on every textarea marked
   data-markdown-editor. Previews come from the server, rendered by the same
   code as the public pages; images go into the image library. Nothing is
   loaded from other sites: the icons are the admin's own sprite. */
(function () {
  "use strict";

  var CJK = /[㐀-䶿一-鿿豈-﫿]/g;
  var LATIN_WORD = /[A-Za-z0-9]+(?:['’.-][A-Za-z0-9]+)*/g;

  function icon(name) {
    return (
      '<svg class="icon icon-' + name + '" aria-hidden="true"><use href="#icon-' + name + '"></use></svg>'
    );
  }

  function csrfToken() {
    if (window.wagtailConfig && window.wagtailConfig.CSRF_TOKEN) {
      return window.wagtailConfig.CSRF_TOKEN;
    }
    var input = document.querySelector("input[name=csrfmiddlewaretoken]");
    return input ? input.value : "";
  }

  /* Chinese characters plus Latin words, as the article head counts them
     (design-details 6.3); addresses and markup are not words. */
  function countWords(text) {
    var bare = text
      .replace(/!?\[([^\]]*)\]\([^)]*\)/g, "$1")
      .replace(/https?:\/\/\S+/g, "");
    return (bare.match(CJK) || []).length + (bare.match(LATIN_WORD) || []).length;
  }

  function insertVideo(editor) {
    var url = window.prompt("粘贴 B 站视频链接（bilibili.com/video/… 或 b23.tv/…）：");
    if (!url || !url.trim()) {
      return;
    }
    editor.codemirror.replaceSelection("\n\n" + url.trim() + "\n\n");
    editor.codemirror.focus();
  }

  function toggleHelp(textarea) {
    var help = textarea.closest(".md-field").querySelector("[data-markdown-help]");
    if (help) {
      help.hidden = !help.hidden;
    }
  }

  function start(textarea) {
    if (textarea.dataset.markdownReady) {
      return;
    }
    textarea.dataset.markdownReady = "1";
    var previewUrl = textarea.dataset.previewUrl;
    var uploadUrl = textarea.dataset.uploadUrl;
    var sequence = 0;
    var timer = null;

    function renderPreview(text, preview) {
      var mine = ++sequence;
      window.clearTimeout(timer);
      timer = window.setTimeout(function () {
        var body = new URLSearchParams();
        body.set("text", text);
        fetch(previewUrl, {
          method: "POST",
          credentials: "same-origin",
          headers: { "X-CSRFToken": csrfToken() },
          body: body,
        })
          .then(function (response) {
            if (!response.ok) {
              throw new Error(String(response.status));
            }
            return response.text();
          })
          .then(function (html) {
            if (mine === sequence) {
              preview.innerHTML = html;
            }
          })
          .catch(function () {
            if (mine === sequence) {
              preview.innerHTML = '<p class="md-preview__error">预览没有生成，稍后再点一次。</p>';
            }
          });
      }, 200);
      return preview.innerHTML || '<p class="md-preview__wait">正在生成预览…</p>';
    }

    function uploadImage(file, onSuccess, onError) {
      var data = new FormData();
      data.append("image", file);
      fetch(uploadUrl, {
        method: "POST",
        credentials: "same-origin",
        headers: { "X-CSRFToken": csrfToken() },
        body: data,
      })
        .then(function (response) {
          return response.json().then(function (json) {
            return { ok: response.ok, json: json };
          });
        })
        .then(function (result) {
          if (result.ok && result.json.url) {
            onSuccess(result.json.url);
          } else {
            onError(result.json.error || "上传失败。");
          }
        })
        .catch(function () {
          onError("上传失败，检查网络后再试。");
        });
    }

    var editor = new window.EasyMDE({
      element: textarea,
      autoDownloadFontAwesome: false,
      spellChecker: false,
      nativeSpellcheck: false,
      forceSync: true,
      minHeight: "320px",
      sideBySideFullscreen: false,
      toolbarButtonClassPrefix: "mde",
      previewClass: ["editor-preview", "md-preview"],
      previewRender: renderPreview,
      promptURLs: true,
      promptTexts: { link: "链接地址：", image: "图片地址：" },
      insertTexts: {
        link: ["[", "](#url#)"],
        image: ["![", "](#url#)"],
        // On a line of its own, so it shows as a figure (design 5.2).
        uploadedImage: ["\n\n![](#url#)\n\n", ""],
        table: ["", "\n\n| 列 1 | 列 2 | 列 3 |\n| --- | --- | --- |\n| 内容 | 内容 | 内容 |\n\n"],
        horizontalRule: ["", "\n\n---\n\n"],
      },
      uploadImage: true,
      imageUploadFunction: uploadImage,
      imageMaxSize: Number(textarea.dataset.maxSize) || 5242880,
      imageAccept: "image/png, image/jpeg, image/gif, image/webp",
      imageTexts: {
        sbInit: "图片可以拖进来或直接粘贴",
        sbOnDragEnter: "松开就上传",
        sbOnDrop: "正在上传 #images_names#…",
        sbProgress: "正在上传 #file_name#：#progress#%",
        sbOnUploaded: "已上传 #image_name#",
        sizeUnits: " B, KB, MB",
      },
      errorMessages: {
        noFileGiven: "没有选中图片。",
        typeNotAllowed: "只能上传 PNG、JPEG、GIF、WebP 图片。",
        fileTooLarge: "#image_name# 有 #image_size#，超过了 #image_max_size#。",
        importError: "#image_name# 上传失败：#error#",
      },
      errorCallback: function (message) {
        window.alert(message);
      },
      status: [
        "upload-image",
        {
          className: "md-words",
          defaultValue: function (el) {
            el.textContent = countWords(textarea.value) + " 字";
          },
          onUpdate: function (el) {
            el.textContent = countWords(editor.value()) + " 字";
          },
        },
      ],
      toolbar: [
        { name: "bold", action: window.EasyMDE.toggleBold, icon: icon("bold"), title: "加粗" },
        { name: "italic", action: window.EasyMDE.toggleItalic, icon: icon("italic"), title: "斜体" },
        {
          name: "strikethrough",
          action: window.EasyMDE.toggleStrikethrough,
          icon: icon("strikethrough"),
          title: "删除线",
        },
        { name: "heading-2", action: window.EasyMDE.toggleHeading2, icon: icon("h2"), title: "二级标题" },
        { name: "heading-3", action: window.EasyMDE.toggleHeading3, icon: icon("h3"), title: "三级标题" },
        "|",
        { name: "quote", action: window.EasyMDE.toggleBlockquote, icon: icon("openquote"), title: "引用" },
        {
          name: "unordered-list",
          action: window.EasyMDE.toggleUnorderedList,
          icon: icon("list-ul"),
          title: "无序列表",
        },
        {
          name: "ordered-list",
          action: window.EasyMDE.toggleOrderedList,
          icon: icon("list-ol"),
          title: "有序列表",
        },
        "|",
        { name: "link", action: window.EasyMDE.drawLink, icon: icon("link"), title: "链接" },
        {
          name: "upload-image",
          action: window.EasyMDE.drawUploadedImage,
          icon: icon("image"),
          title: "图片（上传，也可以拖进来或粘贴）",
        },
        { name: "video", action: insertVideo, icon: icon("media"), title: "B 站视频" },
        { name: "table", action: window.EasyMDE.drawTable, icon: icon("table"), title: "表格" },
        {
          name: "horizontal-rule",
          action: window.EasyMDE.drawHorizontalRule,
          icon: icon("minus"),
          title: "分隔线",
        },
        "|",
        {
          name: "preview",
          action: window.EasyMDE.togglePreview,
          icon: icon("view"),
          title: "预览",
          noDisable: true,
        },
        {
          name: "side-by-side",
          action: window.EasyMDE.toggleSideBySide,
          icon: icon("desktop"),
          title: "并排预览",
          noDisable: true,
          noMobile: true,
        },
        {
          name: "fullscreen",
          action: window.EasyMDE.toggleFullScreen,
          icon: icon("expand-right"),
          title: "全屏",
          noDisable: true,
          noMobile: true,
        },
        "|",
        {
          name: "guide",
          action: function () {
            toggleHelp(textarea);
          },
          icon: icon("help"),
          title: "写法说明",
          noDisable: true,
        },
      ],
    });

    /* Wagtail's unsaved-changes warning and live preview listen to the form. */
    editor.codemirror.on("change", function () {
      textarea.value = editor.value();
      textarea.dispatchEvent(new Event("input", { bubbles: true }));
      textarea.dispatchEvent(new Event("change", { bubbles: true }));
    });

    /* Drawn while hidden (a closed tab or panel), CodeMirror measures nothing. */
    if ("IntersectionObserver" in window) {
      new IntersectionObserver(function (entries) {
        if (entries.some(function (entry) { return entry.isIntersecting; })) {
          editor.codemirror.refresh();
        }
      }).observe(editor.codemirror.getWrapperElement());
    }
  }

  function startAll() {
    if (!window.EasyMDE) {
      return;
    }
    document.querySelectorAll("textarea[data-markdown-editor]").forEach(start);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", startAll);
  } else {
    startAll();
  }
})();
