import React, { useState } from 'react';
import { PageActions } from '../../utils/actions/';
import { MediaPageStore } from '../../utils/stores/';
import { csrfToken, translateString } from '../../utils/helpers/';
import { CircleIconButton, MaterialIcon } from '../_shared/';

function mediaToken() {
  const storeToken = MediaPageStore.get('media-id');

  if (storeToken) {
    return storeToken;
  }

  const mediaElement = document.getElementById('page-media');

  if (mediaElement && mediaElement.dataset && mediaElement.dataset.mediaId) {
    return mediaElement.dataset.mediaId;
  }

  const queryToken = new URLSearchParams(window.location.search).get('m');

  if (queryToken) {
    return queryToken;
  }

  const matches = window.location.pathname.match(/\/media\/([^/]+)/);

  return matches ? matches[1] : null;
}

function postMediaAction(action, body) {
  const token = mediaToken();

  if (!token) {
    return Promise.reject(new Error('Missing media token'));
  }

  return fetch('/api/v1/media/' + encodeURIComponent(token) + '/' + action + '/', {
    method: 'POST',
    credentials: 'same-origin',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': csrfToken(),
    },
    body: body ? JSON.stringify(body) : undefined,
  }).then((response) => {
    if (!response.ok) {
      throw new Error('Request failed');
    }

    return response;
  });
}

function WaicActionButton(props) {
  return (
    <div className={props.className}>
      <button type="button" onClick={props.onClick} disabled={props.disabled}>
        <CircleIconButton type="span">
          <MaterialIcon type={props.icon} />
        </CircleIconButton>
        <span>{props.text}</span>
      </button>
    </div>
  );
}

export function MediaWaicActions() {
  const mediaData = MediaPageStore.get('media-data') || {};
  const [isArchived, setIsArchived] = useState(!!mediaData.is_archived);
  const [isArchiving, setIsArchiving] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [isDenoising, setIsDenoising] = useState(false);
  const showAiActions = MediaPageStore.isVideo();

  function runAction(ev, action, body, setLoading, onSuccess, successMessage, failureMessage) {
    ev.preventDefault();
    ev.stopPropagation();

    setLoading(true);

    postMediaAction(action, body)
      .then(() => {
        onSuccess();
        PageActions.addNotification(successMessage, action + 'Success');
      })
      .catch(() => {
        setLoading(false);
        PageActions.addNotification(failureMessage, action + 'Failure');
      });
  }

  return (
    <>
      <WaicActionButton
        className={'archive' + (isArchived ? ' active' : '')}
        disabled={isArchiving || isArchived}
        icon={isArchived ? 'archive' : 'inventory_2'}
        text={translateString(isArchiving ? 'Archiving...' : isArchived ? 'Archived' : 'Archive')}
        onClick={(ev) =>
          runAction(
            ev,
            'archive',
            { action: 'archive' },
            setIsArchiving,
            () => {
              setIsArchived(true);
              setIsArchiving(false);
            },
            translateString('Media archived'),
            translateString('Failed to archive media')
          )
        }
      />

      {showAiActions ? (
        <WaicActionButton
          className="transcribe"
          disabled={isTranscribing}
          icon="closed_caption"
          text={translateString(isTranscribing ? 'Generating...' : 'AI subtitles')}
          onClick={(ev) =>
            runAction(
              ev,
              'transcribe',
              null,
              setIsTranscribing,
              () => setIsTranscribing(false),
              translateString('AI subtitle generation started'),
              translateString('Failed to start AI subtitle generation')
            )
          }
        />
      ) : null}

      {showAiActions ? (
        <WaicActionButton
          className="denoise"
          disabled={isDenoising}
          icon="hearing"
          text={translateString(isDenoising ? 'Processing...' : 'Denoise')}
          onClick={(ev) =>
            runAction(
              ev,
              'denoise',
              null,
              setIsDenoising,
              () => setIsDenoising(false),
              translateString('Denoise processing started'),
              translateString('Failed to start denoise processing')
            )
          }
        />
      ) : null}
    </>
  );
}
