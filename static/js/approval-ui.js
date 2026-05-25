/**
 * WAIC Approval & Permission UI — v2
 * Injects into media detail page: lock button, approval badge, admin actions.
 * Self-detects permissions via API — no template vars needed.
 */
(function() {
  'use strict';

  var mediaId = window.WAIC_MEDIA_ID;
  if (!mediaId) {
    var m = new URLSearchParams(location.search).get('m');
    if (m) mediaId = m;
  }
  if (!mediaId) return;

  function api(url, body) {
    var xhr = new XMLHttpRequest();
    xhr.open(body ? 'POST' : 'GET', url, false);
    xhr.setRequestHeader('Content-Type', 'application/json');
    var csrf = (document.cookie.match(/(?:^|; )csrftoken=([^;]*)/) || [])[1] || '';
    xhr.setRequestHeader('X-CSRFToken', csrf);
    xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
    if (body) xhr.send(JSON.stringify(body)); else xhr.send();
    try { return JSON.parse(xhr.responseText); } catch(e) { return null; }
  }

  function apiAsync(url, body) {
    return new Promise(function(resolve) {
      var xhr = new XMLHttpRequest();
      xhr.open(body ? 'POST' : 'GET', url, true);
      xhr.setRequestHeader('Content-Type', 'application/json');
      var csrf = (document.cookie.match(/(?:^|; )csrftoken=([^;]*)/) || [])[1] || '';
      xhr.setRequestHeader('X-CSRFToken', csrf);
      xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
      xhr.onload = function() { try { resolve(JSON.parse(xhr.responseText)); } catch(e) { resolve(null); } };
      xhr.onerror = function() { resolve(null); };
      if (body) xhr.send(JSON.stringify(body)); else xhr.send();
    });
  }

  // --- Gather info ---
  var permCheck = api('/api/v1/perm/check/?media_id=' + encodeURIComponent(mediaId));
  var mediaInfo = api('/api/v1/media/' + mediaId);

  var canView = permCheck ? permCheck.can_view : true;
  var isPending = permCheck ? permCheck.pending : false;
  var approvalStatus = mediaInfo && mediaInfo.approval_status !== null && mediaInfo.approval_status !== undefined ? mediaInfo.approval_status : null;
  var isAdmin = approvalStatus !== null;

  // --- Build widget ---
  var container = document.createElement('div');
  container.id = 'waic-approval-widget';
  container.style.cssText = 'position:fixed;bottom:24px;right:24px;z-index:9998;display:flex;flex-direction:column;gap:10px;align-items:flex-end;';

  // 1. Lock button for non-viewers
  if (!canView && !isPending && permCheck) {
    var lockBtn = document.createElement('button');
    lockBtn.className = 'waic-approval-btn waic-approval-lock';
    lockBtn.innerHTML = '<i class="material-icons" style="vertical-align:middle;margin-right:8px;">lock</i> 请求访问权限';
    lockBtn.title = '您没有此素材的查看权限，点击申请';
    lockBtn.onclick = showRequestDialog;
    container.appendChild(lockBtn);
  }

  // 2. Pending badge
  if (isPending) {
    var badge = document.createElement('div');
    badge.className = 'waic-approval-badge';
    badge.innerHTML = '<i class="material-icons" style="vertical-align:middle;margin-right:6px;font-size:18px;">hourglass_empty</i> 访问申请审核中';
    container.appendChild(badge);
  }

  // 3. Admin: approval status + actions
  if (isAdmin && approvalStatus) {
    var statusLabels = {pending:'⏳ 待审批', submitted:'📤 已提交', approved:'✅ 已通过', rejected:'❌ 已驳回'};
    var statusBadge = document.createElement('div');
    statusBadge.className = 'waic-approval-badge waic-approval-' + approvalStatus;
    statusBadge.textContent = statusLabels[approvalStatus] || approvalStatus;
    container.appendChild(statusBadge);

    if (approvalStatus === 'submitted' || approvalStatus === 'pending') {
      var actions = document.createElement('div');
      actions.style.cssText = 'display:flex;gap:8px;';

      var approveBtn = document.createElement('button');
      approveBtn.className = 'waic-approval-btn waic-approval-approve';
      approveBtn.innerHTML = '<i class="material-icons" style="vertical-align:middle;margin-right:6px;font-size:18px;">check</i> 通过';
      approveBtn.onclick = function() { doAction('approve'); };

      var rejectBtn = document.createElement('button');
      rejectBtn.className = 'waic-approval-btn waic-approval-reject';
      rejectBtn.innerHTML = '<i class="material-icons" style="vertical-align:middle;margin-right:6px;font-size:18px;">close</i> 驳回';
      rejectBtn.onclick = function() { doAction('reject'); };

      actions.appendChild(approveBtn);
      actions.appendChild(rejectBtn);
      container.appendChild(actions);
    }
  }

  // --- Request dialog ---
  function showRequestDialog() {
    var overlay = document.createElement('div');
    overlay.className = 'waic-dialog-overlay';
    overlay.innerHTML =
      '<div class="waic-dialog">' +
        '<div class="waic-dialog-header"><strong>申请访问权限</strong><span>素材: ' + mediaId + '</span></div>' +
        '<div class="waic-dialog-body">' +
          '<label class="waic-dialog-label">申请理由（可选）</label>' +
          '<textarea id="waic-req-reason" class="waic-dialog-textarea" placeholder="说明您为什么需要访问此素材..." rows="3"></textarea>' +
        '</div>' +
        '<div class="waic-dialog-footer">' +
          '<button class="waic-dialog-btn-cancel">取消</button>' +
          '<button class="waic-dialog-btn-submit">提交申请</button>' +
        '</div>' +
      '</div>';
    document.body.appendChild(overlay);

    overlay.querySelector('.waic-dialog-btn-cancel').onclick = function() { overlay.remove(); };
    overlay.querySelector('.waic-dialog-btn-submit').onclick = function() {
      var reason = document.getElementById('waic-req-reason').value;
      apiAsync('/api/v1/perm/request/', { media_id: mediaId, reason: reason }).then(function(res) {
        overlay.remove();
        if (res && res.success) {
          toast('✅ 申请已提交，等待管理员审批');
          setTimeout(function() { location.reload(); }, 1000);
        } else {
          toast('❌ ' + ((res && res.error) || '申请失败'));
        }
      });
    };
    overlay.onclick = function(e) { if (e.target === overlay) overlay.remove(); };
  }

  // --- Admin actions ---
  function doAction(action) {
    apiAsync('/api/v1/approval/' + action + '/', { friendly_token: mediaId }).then(function(res) {
      if (res && res.ok) {
        toast(action === 'approve' ? '✅ 已通过' : '❌ 已驳回');
        setTimeout(function() { location.reload(); }, 800);
      } else {
        toast('操作失败: ' + ((res && res.error) || ''));
      }
    });
  }

  // --- Toast ---
  function toast(msg) {
    var t = document.createElement('div');
    t.style.cssText = 'position:fixed;top:80px;left:50%;transform:translateX(-50%);z-index:99999;background:#1e293b;color:#fff;padding:12px 24px;border-radius:10px;font-size:14px;font-weight:600;box-shadow:0 8px 30px rgba(0,0,0,0.2);opacity:0;transition:opacity 0.3s;pointer-events:none;';
    t.textContent = msg;
    document.body.appendChild(t);
    requestAnimationFrame(function() { t.style.opacity = '1'; });
    setTimeout(function() { t.style.opacity = '0'; setTimeout(function() { t.remove(); }, 300); }, 2500);
  }

  // --- Styles ---
  var style = document.createElement('style');
  style.textContent =
    '.waic-approval-btn{display:inline-flex;align-items:center;padding:12px 22px;border:none;border-radius:12px;font-size:14px;font-weight:600;cursor:pointer;transition:all 0.15s;box-shadow:0 4px 14px rgba(0,0,0,0.1);color:#fff;}' +
    '.waic-approval-lock{background:#f59e0b;}.waic-approval-lock:hover{background:#d97706;transform:translateY(-1px);}' +
    '.waic-approval-approve{background:#10b981;}.waic-approval-approve:hover{background:#059669;transform:translateY(-1px);}' +
    '.waic-approval-reject{background:#ef4444;}.waic-approval-reject:hover{background:#dc2626;transform:translateY(-1px);}' +
    '.waic-approval-badge{display:inline-flex;align-items:center;padding:10px 18px;border-radius:10px;font-size:13px;font-weight:600;background:#f1f5f9;color:#475569;box-shadow:0 2px 8px rgba(0,0,0,0.06);}' +
    '.waic-approval-approved{background:#d1fae5;color:#065f46;}' +
    '.waic-approval-rejected{background:#fee2e2;color:#991b1b;}' +
    '.waic-approval-pending,.waic-approval-submitted{background:#fef3c7;color:#92400e;}' +
    '.waic-dialog-overlay{position:fixed;inset:0;z-index:99999;background:rgba(15,23,42,0.6);backdrop-filter:blur(4px);display:flex;align-items:center;justify-content:center;}' +
    '.waic-dialog{background:#fff;border-radius:16px;box-shadow:0 20px 60px rgba(0,0,0,0.2);width:min(420px,calc(100vw-40px));overflow:hidden;}' +
    '.waic-dialog-header{padding:20px 24px 12px;}.waic-dialog-header strong{display:block;font-size:18px;color:#1e293b;}.waic-dialog-header span{display:block;margin-top:4px;font-size:13px;color:#94a3b8;}' +
    '.waic-dialog-body{padding:0 24px 20px;}.waic-dialog-label{display:block;margin-bottom:6px;font-size:13px;font-weight:600;color:#475569;}' +
    '.waic-dialog-textarea{width:100%;padding:10px 14px;border:1px solid #e2e8f0;border-radius:10px;font-size:14px;color:#1e293b;outline:none;box-sizing:border-box;resize:vertical;font-family:inherit;}' +
    '.waic-dialog-textarea:focus{border-color:#3b82f6;box-shadow:0 0 0 3px rgba(59,130,246,0.15);}' +
    '.waic-dialog-footer{padding:0 24px 20px;display:flex;justify-content:flex-end;gap:10px;}' +
    '.waic-dialog-btn-cancel{background:#f1f5f9;color:#475569;border:none;padding:10px 20px;border-radius:10px;font-size:14px;font-weight:500;cursor:pointer;}' +
    '.waic-dialog-btn-cancel:hover{background:#e2e8f0;}' +
    '.waic-dialog-btn-submit{background:#1a56db;color:#fff;border:none;padding:10px 20px;border-radius:10px;font-size:14px;font-weight:600;cursor:pointer;box-shadow:0 2px 8px rgba(26,86,219,0.25);}' +
    '.waic-dialog-btn-submit:hover{background:#1e40af;}';

  // --- Wire up ---
  document.head.appendChild(style);
  if (container.children.length > 0) {
    var tryInject = function() {
      var pm = document.getElementById('page-media');
      if ((pm && pm.children.length > 0) || document.readyState === 'complete') {
        document.body.appendChild(container);
      } else {
        setTimeout(tryInject, 300);
      }
    };
    tryInject();
  }
})();
