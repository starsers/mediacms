/**
 * ImageCropper — Vanilla JS image crop dialog
 * Usage: new ImageCropper(file, { aspectRatio: 1 }).then(blob => upload(blob))
 */
(function() {
  'use strict';

  var ImageCropper = function(file, options) {
    this.file = file;
    this.opts = Object.assign({
      aspectRatio: null,     // null = freeform, 1 = square, 16/9 = widescreen
      maxWidth: 2048,
      quality: 0.92,
      modalZIndex: 10000,
    }, options || {});

    this._resolve = null;
    this._reject = null;

    // Crop state
    this.cropX = 0;
    this.cropY = 0;
    this.cropW = 0;
    this.cropH = 0;
    this.imgNaturalW = 0;
    this.imgNaturalH = 0;
    this.scale = 1;          // display scale (img display size / natural size)

    this._dragging = false;
    this._resizing = false;
    this._resizeHandle = null;
    this._dragStart = { x: 0, y: 0 };
    this._cropStart = { x: 0, y: 0, w: 0, h: 0 };

    return new Promise(this._init.bind(this));
  };

  ImageCropper.prototype._init = function(resolve, reject) {
    this._resolve = resolve;
    this._reject = reject;

    // Read file as data URL
    var reader = new FileReader();
    var self = this;
    reader.onload = function(e) { self._onImageLoad(e.target.result); };
    reader.onerror = function() { reject(new Error('Failed to read image file')); };
    reader.readAsDataURL(this.file);
  };

  ImageCropper.prototype._onImageLoad = function(dataUrl) {
    var self = this;

    // Load image to get natural dimensions
    var img = new Image();
    img.onload = function() {
      self.imgNaturalW = img.naturalWidth;
      self.imgNaturalH = img.naturalHeight;
      self._buildModal(img, dataUrl);
    };
    img.onerror = function() {
      self._reject(new Error('Failed to load image'));
    };
    img.src = dataUrl;
  };

  ImageCropper.prototype._buildModal = function(img, dataUrl) {
    var self = this;
    this.img = img;

    // --- Create DOM ---
    var overlay = document.createElement('div');
    overlay.className = 'ic-overlay';
    overlay.style.zIndex = this.opts.modalZIndex;

    var modal = document.createElement('div');
    modal.className = 'ic-modal';

    // Header
    var header = document.createElement('div');
    header.className = 'ic-header';
    header.innerHTML = '<span class="ic-title">裁切图片</span>' +
      '<span class="ic-subtitle">拖拽选区调整范围</span>';

    // Body: canvas container
    var body = document.createElement('div');
    body.className = 'ic-body';

    this.canvas = document.createElement('canvas');
    this.canvas.className = 'ic-canvas';
    this.ctx = this.canvas.getContext('2d');

    body.appendChild(this.canvas);

    // Footer
    var footer = document.createElement('div');
    footer.className = 'ic-footer';
    footer.innerHTML = '<button class="ic-btn ic-btn-cancel">取消</button>' +
      '<button class="ic-btn ic-btn-confirm">确认裁切</button>';

    modal.appendChild(header);
    modal.appendChild(body);
    modal.appendChild(footer);
    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    // --- Size canvas to fit viewport ---
    this._resizeCanvas();

    // --- Event handler refs (for cleanup) ---
    this._resizeHandler = function() { self._resizeCanvas(); };
    this._mouseMoveHandler = function(e) { self._onMouseMove(e); };
    this._mouseUpHandler = function(e) { self._onMouseUp(e); };
    this._touchMoveHandler = function(e) { self._onTouchMove(e); };
    this._touchEndHandler = function(e) { self._onTouchEnd(e); };

    window.addEventListener('resize', this._resizeHandler);

    // --- Canvas events ---
    this.canvas.addEventListener('mousedown', function(e) { self._onMouseDown(e); });
    this.canvas.addEventListener('touchstart', function(e) { self._onTouchStart(e); }, { passive: false });

    window.addEventListener('mousemove', this._mouseMoveHandler);
    window.addEventListener('mouseup', this._mouseUpHandler);
    window.addEventListener('touchmove', this._touchMoveHandler, { passive: false });
    window.addEventListener('touchend', this._touchEndHandler);

    // Buttons
    modal.querySelector('.ic-btn-cancel').addEventListener('click', function() {
      self._destroy();
      self._reject(new Error('User cancelled'));
    });
    modal.querySelector('.ic-btn-confirm').addEventListener('click', function() {
      self._doCrop();
    });

    // Click overlay to close
    overlay.addEventListener('click', function(e) {
      if (e.target === overlay) {
        self._destroy();
        self._reject(new Error('User cancelled'));
      }
    });

    // Escape key
    this._keyHandler = function(e) {
      if (e.key === 'Escape') {
        self._destroy();
        self._reject(new Error('User cancelled'));
      }
    };
    window.addEventListener('keydown', this._keyHandler);

    // Initial draw
    this._draw();

    // Fade in
    requestAnimationFrame(function() {
      overlay.classList.add('ic-visible');
    });
  };

  ImageCropper.prototype._resizeCanvas = function() {
    var maxW = Math.min(window.innerWidth - 80, 900);
    var maxH = Math.min(window.innerHeight - 220, 600);

    // Fit image within bounds
    var imgW = this.imgNaturalW;
    var imgH = this.imgNaturalH;
    this.scale = Math.min(maxW / imgW, maxH / imgH, 1);

    var displayW = Math.round(imgW * this.scale);
    var displayH = Math.round(imgH * this.scale);

    this.canvas.width = displayW;
    this.canvas.height = displayH;
    this.canvas.style.width = displayW + 'px';
    this.canvas.style.height = displayH + 'px';

    // If crop not set yet, default to centered 80% of image
    if (this.cropW === 0) {
      var margin = 0.1;
      this.cropX = displayW * margin;
      this.cropY = displayH * margin;
      this.cropW = displayW * (1 - 2 * margin);
      this.cropH = displayH * (1 - 2 * margin);

      // Apply aspect ratio if set
      if (this.opts.aspectRatio) {
        var ar = this.opts.aspectRatio;
        if (this.cropW / this.cropH > ar) {
          var newW = this.cropH * ar;
          this.cropX += (this.cropW - newW) / 2;
          this.cropW = newW;
        } else {
          var newH = this.cropW / ar;
          this.cropY += (this.cropH - newH) / 2;
          this.cropH = newH;
        }
      }
    }

    this._draw();
  };

  ImageCropper.prototype._draw = function() {
    var ctx = this.ctx;
    var w = this.canvas.width;
    var h = this.canvas.height;

    // Clear
    ctx.clearRect(0, 0, w, h);

    // Draw image
    ctx.drawImage(this.img, 0, 0, w, h);

    // Dim overlay outside crop area
    ctx.fillStyle = 'rgba(0,0,0,0.55)';
    ctx.fillRect(0, 0, w, h);

    // Clear crop area
    ctx.clearRect(this.cropX, this.cropY, this.cropW, this.cropH);

    // Redraw image in crop area only
    ctx.save();
    ctx.beginPath();
    ctx.rect(this.cropX, this.cropY, this.cropW, this.cropH);
    ctx.clip();
    ctx.drawImage(this.img, 0, 0, w, h);
    ctx.restore();

    // Crop border
    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 2;
    ctx.setLineDash([8, 4]);
    ctx.strokeRect(this.cropX, this.cropY, this.cropW, this.cropH);

    // Corner handles
    var handleSize = 10;
    var handles = [
      { x: this.cropX, y: this.cropY },                          // TL
      { x: this.cropX + this.cropW, y: this.cropY },             // TR
      { x: this.cropX, y: this.cropY + this.cropH },             // BL
      { x: this.cropX + this.cropW, y: this.cropY + this.cropH }, // BR
    ];

    ctx.setLineDash([]);
    handles.forEach(function(p) {
      ctx.fillStyle = '#ffffff';
      ctx.fillRect(p.x - handleSize / 2, p.y - handleSize / 2, handleSize, handleSize);
      ctx.strokeStyle = '#1a56db';
      ctx.lineWidth = 2;
      ctx.strokeRect(p.x - handleSize / 2, p.y - handleSize / 2, handleSize, handleSize);
    });

    // Dimension label
    var naturalCropW = Math.round(this.cropW / this.scale);
    var naturalCropH = Math.round(this.cropH / this.scale);
    var label = naturalCropW + ' × ' + naturalCropH;
    ctx.fillStyle = 'rgba(0,0,0,0.7)';
    var labelW = ctx.measureText(label).width + 16;
    ctx.fillRect(this.cropX + this.cropW / 2 - labelW / 2, this.cropY - 28, labelW, 22);
    ctx.fillStyle = '#ffffff';
    ctx.font = '12px Inter, system-ui, sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(label, this.cropX + this.cropW / 2, this.cropY - 13);
  };

  // --- Hit testing ---
  ImageCropper.prototype._getHandleAt = function(mx, my) {
    var hs = 12;
    var handles = {
      tl: { x: this.cropX, y: this.cropY },
      tr: { x: this.cropX + this.cropW, y: this.cropY },
      bl: { x: this.cropX, y: this.cropY + this.cropH },
      br: { x: this.cropX + this.cropW, y: this.cropY + this.cropH },
    };
    for (var key in handles) {
      var h = handles[key];
      if (mx >= h.x - hs && mx <= h.x + hs && my >= h.y - hs && my <= h.y + hs) {
        return key;
      }
    }
    return null;
  };

  ImageCropper.prototype._inCropArea = function(mx, my) {
    return mx >= this.cropX && mx <= this.cropX + this.cropW &&
           my >= this.cropY && my <= this.cropY + this.cropH;
  };

  ImageCropper.prototype._clampCrop = function() {
    var w = this.canvas.width;
    var h = this.canvas.height;

    if (this.cropX < 0) this.cropX = 0;
    if (this.cropY < 0) this.cropY = 0;
    if (this.cropX + this.cropW > w) this.cropX = w - this.cropW;
    if (this.cropY + this.cropH > h) this.cropY = h - this.cropH;

    // Enforce aspect ratio
    if (this.opts.aspectRatio) {
      var ar = this.opts.aspectRatio;
      if (this.cropW / this.cropH !== ar) {
        if (this.cropW / this.cropH > ar) {
          this.cropW = this.cropH * ar;
        } else {
          this.cropH = this.cropW / ar;
        }
      }
    }
  };

  // --- Mouse / Touch handlers ---
  ImageCropper.prototype._getCanvasPos = function(e) {
    var rect = this.canvas.getBoundingClientRect();
    return {
      x: e.clientX - rect.left,
      y: e.clientY - rect.top
    };
  };

  ImageCropper.prototype._onMouseDown = function(e) {
    e.preventDefault();
    var pos = this._getCanvasPos(e);
    var handle = this._getHandleAt(pos.x, pos.y);

    if (handle) {
      this._resizing = true;
      this._resizeHandle = handle;
      this._dragStart = { x: pos.x, y: pos.y };
      this._cropStart = { x: this.cropX, y: this.cropY, w: this.cropW, h: this.cropH };
    } else if (this._inCropArea(pos.x, pos.y)) {
      this._dragging = true;
      this._dragStart = { x: pos.x, y: pos.y };
      this._cropStart = { x: this.cropX, y: this.cropY };
    }
  };

  ImageCropper.prototype._onMouseMove = function(e) {
    if (!this._dragging && !this._resizing) return;

    var pos = this._getCanvasPos(e);
    var dx = pos.x - this._dragStart.x;
    var dy = pos.y - this._dragStart.y;

    if (this._dragging) {
      this.cropX = this._cropStart.x + dx;
      this.cropY = this._cropStart.y + dy;
    } else if (this._resizing) {
      switch (this._resizeHandle) {
        case 'tl':
          this.cropX = this._cropStart.x + dx;
          this.cropY = this._cropStart.y + dy;
          this.cropW = this._cropStart.w - dx;
          this.cropH = this._cropStart.h - dy;
          break;
        case 'tr':
          this.cropY = this._cropStart.y + dy;
          this.cropW = this._cropStart.w + dx;
          this.cropH = this._cropStart.h - dy;
          break;
        case 'bl':
          this.cropX = this._cropStart.x + dx;
          this.cropW = this._cropStart.w - dx;
          this.cropH = this._cropStart.h + dy;
          break;
        case 'br':
          this.cropW = this._cropStart.w + dx;
          this.cropH = this._cropStart.h + dy;
          break;
      }
    }

    // Min size
    if (this.cropW < 40) this.cropW = 40;
    if (this.cropH < 40) this.cropH = 40;

    this._clampCrop();
    this._draw();
  };

  ImageCropper.prototype._onMouseUp = function() {
    this._dragging = false;
    this._resizing = false;
    this._resizeHandle = null;
  };

  ImageCropper.prototype._onTouchStart = function(e) {
    if (e.touches.length === 1) {
      e.preventDefault();
      var fake = { clientX: e.touches[0].clientX, clientY: e.touches[0].clientY };
      this._onMouseDown(fake);
    }
  };

  ImageCropper.prototype._onTouchMove = function(e) {
    if (e.touches.length === 1) {
      e.preventDefault();
      var fake = { clientX: e.touches[0].clientX, clientY: e.touches[0].clientY };
      this._onMouseMove(fake);
    }
  };

  ImageCropper.prototype._onTouchEnd = function(e) {
    this._onMouseUp();
  };

  // --- Crop and output ---
  ImageCropper.prototype._doCrop = function() {
    var self = this;

    // Convert display coords to natural image coords
    var sx = Math.round(this.cropX / this.scale);
    var sy = Math.round(this.cropY / this.scale);
    var sw = Math.round(this.cropW / this.scale);
    var sh = Math.round(this.cropH / this.scale);

    // Limit output size
    var outW = sw;
    var outH = sh;
    if (outW > this.opts.maxWidth) {
      outH = Math.round(outH * this.opts.maxWidth / outW);
      outW = this.opts.maxWidth;
    }

    // Draw to offscreen canvas
    var outCanvas = document.createElement('canvas');
    outCanvas.width = outW;
    outCanvas.height = outH;
    var outCtx = outCanvas.getContext('2d');
    outCtx.drawImage(this.img, sx, sy, sw, sh, 0, 0, outW, outH);

    // Convert to blob
    var mimeType = this.file.type || 'image/jpeg';
    outCanvas.toBlob(function(blob) {
      self._destroy();
      self._resolve(blob);
    }, mimeType, this.opts.quality);
  };

  ImageCropper.prototype._destroy = function() {
    var overlay = document.querySelector('.ic-overlay');
    if (overlay) {
      overlay.classList.remove('ic-visible');
      setTimeout(function() {
        if (overlay.parentNode) overlay.parentNode.removeChild(overlay);
      }, 200);
    }
    // Clean up window-level event listeners
    if (this._resizeHandler) window.removeEventListener('resize', this._resizeHandler);
    if (this._mouseMoveHandler) window.removeEventListener('mousemove', this._mouseMoveHandler);
    if (this._mouseUpHandler) window.removeEventListener('mouseup', this._mouseUpHandler);
    if (this._touchMoveHandler) window.removeEventListener('touchmove', this._touchMoveHandler);
    if (this._touchEndHandler) window.removeEventListener('touchend', this._touchEndHandler);
    if (this._keyHandler) window.removeEventListener('keydown', this._keyHandler);
  };

  // Expose globally
  window.ImageCropper = ImageCropper;
})();
