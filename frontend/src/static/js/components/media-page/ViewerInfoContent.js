import React, { useState, useEffect } from 'react';
import { SiteContext } from '../../utils/contexts/';
import { useUser, usePopup } from '../../utils/hooks/';
import { PageStore, MediaPageStore } from '../../utils/stores/';
import { PageActions, MediaPageActions } from '../../utils/actions/';
import { formatInnerLink, inEmbeddedApp, publishedOnDate } from '../../utils/helpers/';
import { PopupMain } from '../_shared/';
import CommentsList from '../comments/Comments';
import { replaceString } from '../../utils/helpers/';
import { translateString } from '../../utils/helpers/';

function AiAnalyzingIndicator() {
    const mediaData = MediaPageStore.get('media-data') || {};
    const aiSummary = mediaData.ai_summary;

    if (aiSummary) return null;

    return React.createElement('div', { className: 'ai-analyzing-banner' },
        React.createElement('span', { className: 'ai-analyzing-icon' }, '\u23F3'),
        React.createElement('span', null, translateString('AI is analyzing, please wait...')),
        React.createElement('button', {
            type: 'button',
            className: 'ai-analyzing-refresh',
            onClick: function() { window.location.reload(); }
        }, translateString('Refresh'))
    );
}

function AiAnalysisPanel() {
    const mediaData = MediaPageStore.get('media-data') || {};
    const aiSummary = mediaData.ai_summary;
    const aiMetadata = mediaData.ai_metadata || {};
    const tagsInfo = mediaData.tags_info || [];
    const mediaType = mediaData.media_type;

    const [expanded, setExpanded] = useState(false);

    if (!aiSummary) return null;

    const aiTags = tagsInfo.filter(function(t) { return t.source === 'ai'; });

    const fileMeta = aiMetadata.file_metadata;
    const hasDocMeta = fileMeta && (fileMeta.page_count || fileMeta.author);
    const imageObjects = aiMetadata.objects;
    const hasImageMeta = imageObjects && imageObjects.length;
    const dominantColors = aiMetadata.dominant_colors;

    return React.createElement('div', { className: 'ai-analysis-panel' },
        React.createElement('div', {
            className: 'ai-analysis-header',
            onClick: function() { setExpanded(!expanded); }
        },
            React.createElement('span', { className: 'ai-analysis-title' }, '\uD83E\uDD16 ' + translateString('AI Smart Analysis')),
            React.createElement('span', { className: 'ai-analysis-toggle' }, expanded ? '\u25B2' : '\u25BC')
        ),
        expanded ? React.createElement('div', { className: 'ai-analysis-body' },
            React.createElement('div', { className: 'ai-section' },
                React.createElement('div', { className: 'ai-section-label' }, translateString('Summary')),
                React.createElement('div', { className: 'ai-section-content' }, aiSummary)
            ),
            hasDocMeta ? React.createElement('div', { className: 'ai-section' },
                React.createElement('div', { className: 'ai-section-label' }, '\uD83D\uDCC4 ' + translateString('Document Info')),
                React.createElement('div', { className: 'ai-section-content' },
                    fileMeta.page_count ? React.createElement('span', { className: 'ai-meta-item' }, translateString('Pages') + ': ' + fileMeta.page_count) : null,
                    fileMeta.author ? React.createElement('span', { className: 'ai-meta-item' }, translateString('Author') + ': ' + fileMeta.author) : null
                )
            ) : null,
            hasImageMeta ? React.createElement('div', { className: 'ai-section' },
                React.createElement('div', { className: 'ai-section-label' }, '\uD83D\uDDBC\uFE0F ' + translateString('Image Info')),
                React.createElement('div', { className: 'ai-section-content' },
                    aiMetadata.scene_type ? React.createElement('span', { className: 'ai-meta-item' }, translateString('Scene') + ': ' + aiMetadata.scene_type) : null,
                    hasImageMeta ? React.createElement('span', { className: 'ai-meta-item' }, translateString('Objects') + ': ' + imageObjects.join(', ')) : null,
                    dominantColors && dominantColors.length ? React.createElement('span', { className: 'ai-meta-item' },
                        translateString('Colors') + ': ',
                        dominantColors.map(function(c, i) {
                            return React.createElement('span', { key: i, className: 'ai-color-swatch', style: { backgroundColor: c } });
                        })
                    ) : null
                )
            ) : null,
            aiTags.length ? React.createElement('div', { className: 'ai-section' },
                React.createElement('div', { className: 'ai-section-label' }, '\uD83C\uDFF7\uFE0F ' + translateString('AI Tags')),
                React.createElement('div', { className: 'ai-tags-list' },
                    aiTags.map(function(tag, i) {
                        return React.createElement('span', { key: i, className: 'tag-ai', title: translateString('Confidence') + ': ' + Math.round((tag.confidence || 0) * 100) + '%' },
                            '\uD83E\uDD16 ' + tag.title + ' ' + React.createElement('small', null, Math.round((tag.confidence || 0) * 100) + '%')
                        );
                    })
                )
            ) : null
        ) : null
    );
}

function metafield(arr) {
    let i;
    let sep;
    let ret = [];

    if (arr && arr.length) {
        i = 0;
        sep = 1 < arr.length ? ', ' : '';
        while (i < arr.length) {
            ret[i] = (
                <div key={i}>
                    <a href={arr[i].url} title={arr[i].title}>
                        {arr[i].title}
                    </a>
                    {i < arr.length - 1 ? sep : ''}
                </div>
            );
            i += 1;
        }
    }

    return ret;
}

function MediaAuthorBanner(props) {
    return (
        <div className="media-author-banner">
            <div>
                <a className="author-banner-thumb" href={props.link || null} title={props.name}>
                    <span style={{ backgroundImage: 'url(' + props.thumb + ')' }}>
                        <img src={props.thumb} loading="lazy" alt={props.name} title={props.name} />
                    </span>
                </a>
            </div>
            <div>
                <span>
                    <a href={props.link} className="author-banner-name" title={props.name}>
                        <span>{props.name}</span>
                    </a>
                </span>
                {PageStore.get('config-media-item').displayPublishDate && props.published ? (
                    <span className="author-banner-date">
                        {translateString('Published on')} {replaceString(publishedOnDate(new Date(props.published)))}
                    </span>
                ) : null}
            </div>
        </div>
    );
}

function MediaMetaField(props) {
    return (
        <div className={props.id.trim() ? 'media-content-' + props.id.trim() : null}>
            <div className="media-content-field">
                <div className="media-content-field-label">
                    <h4>{props.title}</h4>
                </div>
                <div className="media-content-field-content">{props.value}</div>
            </div>
        </div>
    );
}

function EditMediaButton(props) {
    let link = props.link;

    if (window.MediaCMS.site.devEnv) {
        link = '/edit-media.html';
    }

    if (link && inEmbeddedApp()) {
        link += '&mode=lms_embed_mode';
    }

    return (
        <a href={link} rel="nofollow" title={translateString('Edit media')} className="edit-media-icon">
            <i className="material-icons">edit</i>
        </a>
    );
}

export default function ViewerInfoContent(props) {
    const { userCan } = useUser();

    const description = props.description.trim();
    const tagsContent =
        !PageStore.get('config-enabled').taxonomies.tags || PageStore.get('config-enabled').taxonomies.tags.enabled
            ? metafield(MediaPageStore.get('media-tags'))
            : [];
    let mediaCategories = MediaPageStore.get('media-categories');

    // Filter to show only LMS courses when in embed mode
    if (inEmbeddedApp()) {
        mediaCategories = mediaCategories.filter(cat => cat.is_lms_course === true);
    }

    const categoriesContent = PageStore.get('config-options').pages.media.categoriesWithTitle
        ? []
        : !PageStore.get('config-enabled').taxonomies.categories ||
            PageStore.get('config-enabled').taxonomies.categories.enabled
          ? metafield(mediaCategories)
          : [];

    let summary = MediaPageStore.get('media-summary');

    summary = summary ? summary.trim() : '';

    const [popupContentRef, PopupContent, PopupTrigger] = usePopup();

    const [hasSummary, setHasSummary] = useState('' !== summary);
    const [isContentVisible, setIsContentVisible] = useState('' == summary);

    function proceedMediaRemoval() {
        MediaPageActions.removeMedia();
        popupContentRef.current.toggle();
    }

    function cancelMediaRemoval() {
        popupContentRef.current.toggle();
    }

    function onMediaDelete(mediaId) {
        // FIXME: Without delay creates conflict [ Uncaught Error: Dispatch.dispatch(...): Cannot dispatch in the middle of a dispatch. ].
        setTimeout(function () {
            PageActions.addNotification('Media removed. Redirecting...', 'mediaDelete');
            setTimeout(function () {
                window.location.href =
                    SiteContext._currentValue.url +
                    '/' +
                    MediaPageStore.get('media-data').author_profile.replace(/^\//g, '');
            }, 2000);
        }, 100);

        if (void 0 !== mediaId) {
            console.info("Removed media '" + mediaId + '"');
        }
    }

    function onMediaDeleteFail(mediaId) {
        // FIXME: Without delay creates conflict [ Uncaught Error: Dispatch.dispatch(...): Cannot dispatch in the middle of a dispatch. ].
        setTimeout(function () {
            PageActions.addNotification('Media removal failed', 'mediaDeleteFail');
        }, 100);

        if (void 0 !== mediaId) {
            console.info('Media "' + mediaId + '"' + ' removal failed');
        }
    }

    function onClickLoadMore() {
        setIsContentVisible(!isContentVisible);
    }

    function onTimestampClick(e) {
        const target = e.target.closest('.video-timestamp');
        if (!target) return;
        e.preventDefault();
        const seconds = parseFloat(target.getAttribute('data-timestamp'));
        if (isNaN(seconds)) return;
        // Try VideoJS player first, then native video element
        const vjsEl = document.querySelector('.video-js');
        if (vjsEl && vjsEl.player) {
            vjsEl.player.currentTime(seconds);
            vjsEl.player.play();
        } else {
            const video = document.querySelector('video');
            if (video) {
                video.currentTime = seconds;
                video.play();
            }
        }
    }

    useEffect(() => {
        MediaPageStore.on('media_delete', onMediaDelete);
        MediaPageStore.on('media_delete_fail', onMediaDeleteFail);
        document.addEventListener('click', onTimestampClick);
        return () => {
            MediaPageStore.removeListener('media_delete', onMediaDelete);
            MediaPageStore.removeListener('media_delete_fail', onMediaDeleteFail);
            document.removeEventListener('click', onTimestampClick);
        };
    }, []);

    const authorLink = formatInnerLink(props.author.url, SiteContext._currentValue.url);
    const authorThumb = formatInnerLink(props.author.thumb, SiteContext._currentValue.url);

    function setTimestampAnchors(text) {
        function wrapTimestampWithAnchor(match, string) {
            let split = match.split(':'),
                s = 0,
                m = 1;

            while (split.length > 0) {
                s += m * parseInt(split.pop(), 10);
                m *= 60;
            }

            const wrapped = `<a href="#" data-timestamp="${s}" class="video-timestamp">${match}</a>`;
            return wrapped;
        }

        const timeRegex = new RegExp('((\\d)?\\d:)?(\\d)?\\d:\\d\\d', 'g');
        return text.replace(timeRegex, wrapTimestampWithAnchor);
    }

    return (
        <div className="media-info-content">
            {void 0 === PageStore.get('config-media-item').displayAuthor ||
            null === PageStore.get('config-media-item').displayAuthor ||
            !!PageStore.get('config-media-item').displayAuthor ? (
                <MediaAuthorBanner
                    link={authorLink}
                    thumb={authorThumb}
                    name={props.author.name}
                    published={props.published}
                />
            ) : null}

            <div className="media-content-banner">
                <div className="media-content-banner-inner">
                    {hasSummary ? <div className="media-content-summary">{summary}</div> : null}
                    {(!hasSummary || isContentVisible) && description ? (
                        <div
                            className="media-content-description"
                            dangerouslySetInnerHTML={{ __html: setTimestampAnchors(description) }}
                        ></div>
                    ) : null}
                    {hasSummary ? (
                        <button className="load-more" onClick={onClickLoadMore}>
                            {isContentVisible ? 'SHOW LESS' : 'SHOW MORE'}
                        </button>
                    ) : null}
                    {tagsContent.length ? (
                        <MediaMetaField
                            value={tagsContent}
                            title={1 < tagsContent.length ? translateString('Tags') : translateString('Tag')}
                            id="tags"
                        />
                    ) : null}
                    {categoriesContent.length ? (
                        <MediaMetaField
                            value={categoriesContent}
                            title={
                                inEmbeddedApp()
                                    ? (1 < categoriesContent.length
                                        ? translateString('Courses')
                                        : translateString('Course'))
                                    : (1 < categoriesContent.length
                                        ? translateString('Categories')
                                        : translateString('Category'))
                            }
                            id="categories"
                        />
                    ) : null}

                    {userCan.editMedia ? (
                        <div className="media-author-actions">
                            {userCan.editMedia ? (
                                <EditMediaButton link={MediaPageStore.get('media-data').edit_url} />
                            ) : null}

                            {userCan.deleteMedia ? (
                                <PopupTrigger contentRef={popupContentRef}>
                                    <button className="remove-media-icon" title={translateString('Delete media')}>
                                        <i className="material-icons">delete</i>
                                    </button>
                                </PopupTrigger>
                            ) : null}

                            {userCan.deleteMedia ? (
                                <PopupContent contentRef={popupContentRef}>
                                    <PopupMain>
                                        <div className="popup-message">
                                            <span className="popup-message-title">Media removal</span>
                                            <span className="popup-message-main">
                                                You're willing to remove media permanently?
                                            </span>
                                        </div>
                                        <hr />
                                        <span className="popup-message-bottom">
                                            <button
                                                className="button-link cancel-comment-removal"
                                                onClick={cancelMediaRemoval}
                                            >
                                                CANCEL
                                            </button>
                                            <button
                                                className="button-link proceed-comment-removal"
                                                onClick={proceedMediaRemoval}
                                            >
                                                PROCEED
                                            </button>
                                        </span>
                                    </PopupMain>
                                </PopupContent>
                            ) : null}
                        </div>
                    ) : null}
                </div>
            </div>

            <AiAnalyzingIndicator />
            <AiAnalysisPanel />

            <CommentsList />
        </div>
    );
}
