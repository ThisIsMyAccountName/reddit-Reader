// Track collapsed comment state per post
const postCommentStates = new Map();

// Back to top button
(function() {
    const backToTop = document.getElementById('back-to-top');
    let ticking = false;
    
    function updateBackToTop() {
        if (window.scrollY > 500) {
            backToTop.classList.add('visible');
        } else {
            backToTop.classList.remove('visible');
        }
        ticking = false;
    }
    
    window.addEventListener('scroll', () => {
        if (!ticking) {
            requestAnimationFrame(updateBackToTop);
            ticking = true;
        }
    });
    
    backToTop.addEventListener('click', () => {
        window.scrollTo({ top: 0, behavior: 'smooth' });
    });
})();

// Header hide/show on scroll and mouse
(function() {
    const header = document.querySelector('.header');
    let lastScrollY = window.scrollY;
    let ticking = false;
    let scrollUpDistance = 0;
    let scrollDownDistance = 0;
    const SHOW_HEADER_THRESHOLD = 150; // Pixels to scroll up before showing header
    const HIDE_HEADER_THRESHOLD = 150; // Pixels to scroll down before hiding header

    function updateHeader() {
        const currentScrollY = window.scrollY;
        const scrollDelta = currentScrollY - lastScrollY;
        
        // Always show at very top
        if (currentScrollY <= 50) {
            header.classList.remove('header-hidden');
            scrollUpDistance = 0;
            scrollDownDistance = 0;
        } 
        // Scrolling down
        else if (scrollDelta > 0) {
            scrollDownDistance += scrollDelta;
            scrollUpDistance = 0;
            if (scrollDownDistance > HIDE_HEADER_THRESHOLD) {
                header.classList.add('header-hidden');
                // Close mobile menus when header hides
                document.getElementById('header-search-form')?.classList.remove('active');
                document.getElementById('header-auth-menu')?.classList.remove('active');
            }
        }
        // Scrolling up
        else if (scrollDelta < 0) {
            scrollUpDistance -= scrollDelta;
            scrollDownDistance = 0;
            if (scrollUpDistance > SHOW_HEADER_THRESHOLD) {
                header.classList.remove('header-hidden');
            }
        }
        
        lastScrollY = currentScrollY;
        ticking = false;
    }
    
    window.addEventListener('scroll', () => {
        if (!ticking) {
            requestAnimationFrame(updateHeader);
            ticking = true;
        }
    });
    
    // Show header when mouse moves to top of viewport
    document.addEventListener('mousemove', (e) => {
        if (e.clientY <= 50) {
            header.classList.remove('header-hidden');
        }
    });

    // Mobile menu toggles
    const searchToggle = document.getElementById('mobile-search-toggle');
    const menuToggle = document.getElementById('mobile-menu-toggle');
    const searchForm = document.getElementById('header-search-form');
    const authMenu = document.getElementById('header-auth-menu');

    if (searchToggle && searchForm) {
        searchToggle.addEventListener('click', (e) => {
            e.stopPropagation();
            searchForm.classList.toggle('active');
            authMenu?.classList.remove('active');
            if (searchForm.classList.contains('active')) {
                setTimeout(() => searchForm.querySelector('input')?.focus(), 100);
            }
        });
    }

    if (menuToggle && authMenu) {
        menuToggle.addEventListener('click', (e) => {
            e.stopPropagation();
            authMenu.classList.toggle('active');
            searchForm?.classList.remove('active');
        });
    }

    // Close menus when clicking outside
    document.addEventListener('click', (e) => {
        if (!header.contains(e.target)) {
            searchForm?.classList.remove('active');
            authMenu?.classList.remove('active');
        }
    });
})();

/* 
 * GLOBAL COMMENT COLLAPSING LOGIC
 * Handles individual comment thread collapsing.
 */
document.addEventListener('click', (event) => {
    // Check if we clicked a comment (but NOT a link inside it)
    const comment = event.target.closest('.comment');
    if (!comment) return;
    
    // Ignore if clicking links/buttons inside comment
    if (event.target.closest('a, button, input, select')) return;

    // Stop propagation to prevent bubbling to post expanders
    event.stopPropagation();
    
    // Allow selecting text without collapsing
    if (window.getSelection().toString().length > 0) return;

    // Toggle collapsed class
    comment.classList.toggle('collapsed');
});

/*
 * SINGLE-POST META ACTIONS
 * Mirrors the mobile condensed actions menu from the feed page.
 */
(function() {
    // Feed page has its own implementation in posts.js.
    if (document.getElementById('posts-container')) return;

    const singlePost = document.querySelector('.single-post');
    if (!singlePost) return;

    function setupShareButtons(root = document) {
        const shareBtns = root.querySelectorAll('.share-btn');
        shareBtns.forEach(btn => {
            if (btn._shareHandlerAttached) return;
            btn._shareHandlerAttached = true;
            btn.addEventListener('click', async (e) => {
                if (e.button !== 0 || e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) return;
                e.preventDefault();
                e.stopPropagation();
                const path = btn.getAttribute('data-share-path') || '';
                const url = path.startsWith('http') ? path : (window.location.origin + path);
                try {
                    if (navigator.clipboard && navigator.clipboard.writeText) {
                        await navigator.clipboard.writeText(url);
                    } else {
                        const ta = document.createElement('textarea');
                        ta.value = url;
                        document.body.appendChild(ta);
                        ta.select();
                        document.execCommand('copy');
                        document.body.removeChild(ta);
                    }
                    const original = btn.textContent;
                    btn.textContent = '✅';
                    btn.disabled = true;
                    setTimeout(() => {
                        btn.textContent = original;
                        btn.disabled = false;
                    }, 1500);
                } catch (err) {
                    console.error('Copy failed', err);
                }
            });
        });
    }

    function closeMetaMenus() {
        document.querySelectorAll('.single-post .meta-menu').forEach(menu => {
            if (!menu.hidden) {
                menu.hidden = true;
                menu.setAttribute('aria-hidden', 'true');
            }
        });
        document.querySelectorAll('.single-post .meta-menu-toggle').forEach(toggle => {
            toggle.setAttribute('aria-expanded', 'false');
        });
    }

    setupShareButtons(document);

    document.addEventListener('click', (e) => {
        const toggle = e.target.closest('.single-post .meta-menu-toggle');
        if (toggle) {
            e.stopPropagation();
            const post = toggle.closest('.single-post');
            if (!post) return;
            const menu = post.querySelector('.meta-menu');
            const actions = post.querySelector('.post-meta-actions');
            if (!menu || !actions) return;

            if (menu.hidden) {
                closeMetaMenus();

                menu.innerHTML = actions.innerHTML;
                menu.querySelectorAll('.post-upvotes').forEach(n => n.remove());

                menu.querySelectorAll('.meta-action-btn, form.inline-form').forEach(node => {
                    if (node.tagName === 'FORM') {
                        const btn = node.querySelector('button');
                        if (btn) {
                            let labelText = '';
                            if (btn.classList.contains('pin-btn')) labelText = 'Pin';
                            else if (btn.classList.contains('unpin-btn')) labelText = 'Unpin';
                            else if (btn.classList.contains('ban-btn')) labelText = 'Ban';
                            else labelText = (btn.getAttribute('title') || btn.getAttribute('aria-label') || btn.textContent || '').trim();

                            if (!btn.querySelector('.meta-action-label')) {
                                const span = document.createElement('span');
                                span.className = 'meta-action-label';
                                span.textContent = labelText ? (' ' + labelText) : '';
                                btn.appendChild(span);
                            }
                        }
                    } else {
                        let labelText = '';
                        if (node.classList && node.classList.contains('pin-btn')) labelText = 'Pin';
                        else if (node.classList && node.classList.contains('unpin-btn')) labelText = 'Unpin';
                        else if (node.classList && node.classList.contains('ban-btn')) labelText = 'Ban';
                        else labelText = (node.getAttribute('title') || node.getAttribute('aria-label') || node.textContent || '').trim();

                        if (!node.querySelector('.meta-action-label')) {
                            const span = document.createElement('span');
                            span.className = 'meta-action-label';
                            span.textContent = labelText ? (' ' + labelText) : '';
                            node.appendChild(span);
                        }
                    }
                });

                menu.hidden = false;
                menu.setAttribute('aria-hidden', 'false');
                toggle.setAttribute('aria-expanded', 'true');
                setupShareButtons(menu);

                menu.style.right = 'auto';
                const toggleRect = toggle.getBoundingClientRect();
                const postRect = post.getBoundingClientRect();
                let left = toggleRect.left - postRect.left;
                const top = toggleRect.bottom - postRect.top;

                menu.style.left = left + 'px';
                menu.style.top = top + 'px';

                const menuRect = menu.getBoundingClientRect();
                const overflowRight = menuRect.right - postRect.right;
                if (overflowRight > 0) {
                    left = left - overflowRight - 8;
                    menu.style.left = Math.max(8, left) + 'px';
                }

                const updatedMenuRect = menu.getBoundingClientRect();
                if (updatedMenuRect.left < postRect.left + 8) {
                    menu.style.left = '8px';
                }
            } else {
                closeMetaMenus();
            }
            return;
        }

        if (!e.target.closest('.single-post .meta-menu')) {
            closeMetaMenus();
        }
    }, true);

    window.addEventListener('resize', () => {
        if (window.innerWidth > 480) {
            closeMetaMenus();
        }
    });
})();


function buildDownloadEndpoint(button) {
    const sourceUrl = button.dataset.downloadUrl || '';
    const filename = button.dataset.downloadFilename || '';
    const title = button.dataset.postTitle || '';
    const postId = button.dataset.postId || '';

    const params = new URLSearchParams({
        url: sourceUrl,
        filename,
        title,
        post_id: postId,
    });
    return `/api/download?${params.toString()}`;
}

// Basic HTML escape helper used for client-rendered comment fallbacks
function escapeHTML(str) {
    if (str === null || str === undefined) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

async function triggerDownload(button) {
    const endpoint = buildDownloadEndpoint(button);

    try {
        const response = await fetch(endpoint, { credentials: 'same-origin' });
        if (!response.ok) {
            const payload = await response.json().catch(() => ({}));
            const message = payload.error || 'Download failed';
            throw new Error(message);
        }

        const filename = button.dataset.downloadFilename || 'media.bin';
        const blob = await response.blob();
        const objectUrl = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = objectUrl;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        link.remove();
        URL.revokeObjectURL(objectUrl);
    } catch (err) {
        console.error('Download failed', err);
        alert(err.message || 'Download failed. Please try again.');
    }
}

document.addEventListener('click', async (event) => {
    const downloadBtn = event.target.closest('.download-action');
    if (!downloadBtn) return;

    event.preventDefault();
    event.stopPropagation();

    if (downloadBtn.disabled) return;

    const originalText = downloadBtn.textContent;
    downloadBtn.disabled = true;
    downloadBtn.textContent = '…';
    await triggerDownload(downloadBtn);
    downloadBtn.textContent = originalText;
    downloadBtn.disabled = false;
});

function createCommentElement(comment, depth = 0, showAuthor = true) {
    const item = document.createElement('div');
    item.className = depth > 0 ? 'comment compact comment-reply' : 'comment compact';
    item.dataset.depth = depth;
    item.dataset.commentId = comment.id || '';

    // Content container
    const contentDiv = document.createElement('div');
    contentDiv.className = 'comment-content';

    const score = document.createElement('span');
    score.className = 'comment-score';
    score.textContent = `⬆️ ${comment.score.toLocaleString()}`;

    const meta = document.createElement('div');
    meta.className = 'comment-meta-right';
    if (showAuthor) {
        const authorName = comment.author || '[deleted]';
        if (authorName !== '[deleted]') {
            const authorLink = document.createElement('a');
            authorLink.className = 'comment-author';
            authorLink.href = `/u/${encodeURIComponent(authorName)}`;
            authorLink.textContent = `u/${authorName}`;
            meta.appendChild(authorLink);
        } else {
            const author = document.createElement('span');
            author.className = 'comment-author';
            author.textContent = `u/${authorName}`;
            meta.appendChild(author);
        }
    }
    meta.appendChild(score);

    const body = document.createElement('div');
    body.className = 'comment-body';
    // Use server-provided formatted HTML when available (it's produced
    // by `format_content` server-side). If missing, escape raw body
    // text before inserting to avoid XSS.
    body.innerHTML = comment.formatted_body || escapeHTML(comment.body || '').replace(/\n/g, '<br>');

    contentDiv.appendChild(meta);
    contentDiv.appendChild(body);

    // Add replies if present
    if (comment.replies && comment.replies.length > 0) {
        const repliesDiv = document.createElement('div');
        repliesDiv.className = 'comment-replies';
        repliesDiv.setAttribute('hidden', '');
        
        comment.replies.forEach(reply => {
            repliesDiv.appendChild(createCommentElement(reply, depth + 1, showAuthor));
        });
        
        contentDiv.appendChild(repliesDiv);
    }

    item.appendChild(contentDiv);
    return item;
}

// Gallery navigation removed — preview/peek shows second image below the main image

// Video player controls
document.addEventListener('DOMContentLoaded', () => {
    // Comment expand/collapse (click anywhere on comment to toggle)
    document.addEventListener('click', (event) => {
        const comment = event.target.closest('.comment');
        if (!comment) return;

        // Don't toggle if clicking on links, buttons, or inputs
        if (event.target.closest('a, button, input')) return;

        const repliesContainer = comment.querySelector(':scope > .comment-content > .comment-replies');

        if (!repliesContainer) return;

        const isHidden = repliesContainer.hasAttribute('hidden');
        
        if (isHidden) {
            repliesContainer.removeAttribute('hidden');
        } else {
            repliesContainer.setAttribute('hidden', '');
        }
    });

    // Initialize videos and media resizers
    initVideoControls(document);
    initMediaResizers(document);
});

// Listen for dynamically added posts (infinite scroll)
document.addEventListener('newPostsAdded', (event) => {
    const container = event.detail?.container || document;
    initVideoControls(container);
    initMediaResizers(container);
});

// Gallery toggle: one explicit button for expand/collapse
document.addEventListener('click', (e) => {
    const toggleButton = e.target.closest('.gallery-toggle-btn');
    if (!toggleButton) return;

    const gallery = toggleButton.closest('.gallery');
    if (!gallery) return;

    const post = gallery.closest('.post');
    if (post && window.markPostRead) window.markPostRead(post);

    e.stopPropagation();
    if (gallery.classList.contains('expanded')) {
        collapseGallery(gallery);
    } else {
        expandGallery(gallery);
    }
}, true);

function setGalleryExpandedState(gallery, expanded) {
    const toggleButton = gallery.querySelector('.gallery-toggle-btn');
    if (toggleButton) toggleButton.setAttribute('aria-expanded', expanded ? 'true' : 'false');
}

// Smooth expand: measure real height, animate max-height, then set to none
function expandGallery(gallery) {
    // Record scroll position so we can keep the gallery top in place
    const rect = gallery.getBoundingClientRect();
    const topBefore = rect.top;

    const collapsedMaxHeight = gallery.style.maxHeight;

    // Temporarily remove max-height to measure full content height
    gallery.style.transition = 'none';
    gallery.style.maxHeight = 'none';
    const fullHeight = gallery.scrollHeight;
    // Restore collapsed max-height instantly
    gallery.style.maxHeight = collapsedMaxHeight;
    // Force reflow so the browser registers the starting value
    void gallery.offsetHeight;
    // Now animate to the full height
    gallery.style.transition = '';
    gallery.style.maxHeight = fullHeight + 'px';

    gallery.classList.add('expanded');
    setGalleryExpandedState(gallery, true);

    // After transition, remove max-height so resized images aren't clipped
    const onEnd = () => {
        gallery.removeEventListener('transitionend', onEnd);
        if (gallery.classList.contains('expanded')) {
            gallery.style.maxHeight = 'none';
        }
    };
    gallery.addEventListener('transitionend', onEnd);

    // Keep the gallery top at the same viewport position
    const topAfter = gallery.getBoundingClientRect().top;
    if (Math.abs(topAfter - topBefore) > 2) {
        window.scrollBy({ top: topAfter - topBefore, behavior: 'smooth' });
    }

    // Init resizers on newly-visible images
    initMediaResizers(gallery);
}

const READ_MEDIA_SCALE = 0.5;

function getDefaultCollapsedGalleryHeight(gallery) {
    const cssMaxHeight = parseFloat(getComputedStyle(gallery).maxHeight);
    if (Number.isFinite(cssMaxHeight) && cssMaxHeight > 0) return cssMaxHeight;
    return 650;
}

function getReadCollapsedGalleryHeight(gallery) {
    if (!gallery.dataset.readBaseMaxHeight) {
        gallery.dataset.readBaseMaxHeight = String(getDefaultCollapsedGalleryHeight(gallery));
    }
    const base = parseFloat(gallery.dataset.readBaseMaxHeight);
    if (!Number.isFinite(base) || base <= 0) return getDefaultCollapsedGalleryHeight(gallery);
    return Math.max(1, Math.round(base * READ_MEDIA_SCALE));
}

function getTargetCollapsedGalleryHeightStyle(gallery) {
    const post = gallery.closest('.post');
    const postId = post?.dataset?.postId;
    const isReadLike = Boolean(
        post && (
            post.classList.contains('post-read') ||
            (postId && _interactedPostIds.has(postId))
        )
    );
    if (isReadLike) {
        return getReadCollapsedGalleryHeight(gallery) + 'px';
    }
    return '';
}

function getCollapsedGalleryHeightForScroll(gallery, targetStyleValue) {
    if (targetStyleValue && targetStyleValue.endsWith('px')) {
        const px = parseFloat(targetStyleValue);
        if (Number.isFinite(px) && px > 0) return px;
    }
    return getDefaultCollapsedGalleryHeight(gallery);
}

function parseTransitionTimeToMs(value) {
    const trimmed = String(value || '').trim();
    if (!trimmed) return 0;
    if (trimmed.endsWith('ms')) return parseFloat(trimmed) || 0;
    if (trimmed.endsWith('s')) return (parseFloat(trimmed) || 0) * 1000;
    return parseFloat(trimmed) || 0;
}

function getMaxHeightTransitionDurationMs(element) {
    const styles = getComputedStyle(element);
    const props = styles.transitionProperty.split(',').map(s => s.trim());
    const durations = styles.transitionDuration.split(',').map(parseTransitionTimeToMs);
    if (!props.length || !durations.length) return 0;

    const maxHeightIndex = props.findIndex(prop => prop === 'max-height' || prop === 'all');
    if (maxHeightIndex >= 0) {
        return durations[maxHeightIndex] ?? durations[durations.length - 1] ?? 0;
    }
    return durations[0] ?? 0;
}

function getVisibleHeaderOffset() {
    const header = document.querySelector('.header');
    if (!header || header.classList.contains('header-hidden')) return 0;
    const rect = header.getBoundingClientRect();
    return rect.bottom > 0 ? rect.bottom : 0;
}

function getCollapsedGalleryScrollTarget(gallery, collapsedTargetStyle) {
    const anchorPadding = 22;
    const anchorOffset = getVisibleHeaderOffset() + anchorPadding;
    const galleryTop = window.scrollY + gallery.getBoundingClientRect().top;
    const collapsedHeight = getCollapsedGalleryHeightForScroll(gallery, collapsedTargetStyle);
    const galleryBottom = galleryTop + collapsedHeight;
    return Math.max(0, galleryBottom - anchorOffset);
}

let collapseScrollAnimationId = null;

function animateCollapseScroll(targetY, durationMs) {
    if (collapseScrollAnimationId !== null) {
        cancelAnimationFrame(collapseScrollAnimationId);
        collapseScrollAnimationId = null;
    }

    const startY = window.scrollY;
    const delta = targetY - startY;
    if (Math.abs(delta) < 1) {
        window.scrollTo(0, targetY);
        return;
    }

    const duration = Math.max(120, durationMs || 0);
    const start = performance.now();

    const step = (now) => {
        const t = Math.min(1, (now - start) / duration);
        // Match CSS ease-out feel so viewport and collapse motion read as one action.
        const eased = 1 - Math.pow(1 - t, 3);
        window.scrollTo(0, Math.round(startY + delta * eased));
        if (t < 1) {
            collapseScrollAnimationId = requestAnimationFrame(step);
        } else {
            collapseScrollAnimationId = null;
        }
    };

    collapseScrollAnimationId = requestAnimationFrame(step);
}

// Smooth collapse: animate max-height back to CSS default, then anchor collapsed gallery in view
function collapseGallery(gallery) {
    // Get current expanded height
    const fullHeight = gallery.scrollHeight;
    // Set explicit max-height so transition has a starting point
    gallery.style.transition = 'none';
    gallery.style.maxHeight = fullHeight + 'px';
    void gallery.offsetHeight;
    // Now animate back to collapsed height (CSS value)
    const collapsedTarget = getTargetCollapsedGalleryHeightStyle(gallery);
    gallery.style.transition = '';
    gallery.style.maxHeight = collapsedTarget;
    const collapseDurationMs = getMaxHeightTransitionDurationMs(gallery) || 400;

    gallery.classList.remove('expanded');
    setGalleryExpandedState(gallery, false);

    // Start scroll immediately with duration synced to the collapse transition.
    const immediateTarget = getCollapsedGalleryScrollTarget(gallery, collapsedTarget);
    animateCollapseScroll(immediateTarget, collapseDurationMs);

    const onEnd = (event) => {
        if (event.target !== gallery || event.propertyName !== 'max-height') return;
        gallery.removeEventListener('transitionend', onEnd);
        // Correct final position after animation in case layout shifted during collapse.
        const finalTarget = getCollapsedGalleryScrollTarget(gallery, collapsedTarget);
        window.scrollTo(0, finalTarget);
    };

    gallery.addEventListener('transitionend', onEnd);
}

// Allow ESC to collapse any expanded galleries
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' || e.key === 'Esc') {
        document.querySelectorAll('.gallery.expanded').forEach(gallery => {
            collapseGallery(gallery);
        });
    }
});

// ── Feature toggle helper ──
// Features default to enabled; users can disable them in Settings.
function isFeatureEnabled(key) {
    const v = localStorage.getItem('feature_' + key);
    return v === null ? true : v === 'true';
}

// ── Feature: "Read" Post Dimming ──
// Posts the user interacted with get dimmed only after they scroll out of view.
// Read IDs stored in sessionStorage so they reset each session.
// "Interacted" IDs are tracked separately; the .post-read class is applied
// by an IntersectionObserver once the post leaves the viewport.
function getReadPosts() {
    try { return new Set(JSON.parse(sessionStorage.getItem('readPosts') || '[]')); }
    catch { return new Set(); }
}
function saveReadPosts(set) {
    try { sessionStorage.setItem('readPosts', JSON.stringify([...set])); } catch {}
}

function clearReadVisualState(postEl) {
    if (!postEl) return;
    postEl.classList.remove('post-read');
}

function undimPostUntilExit(postEl) {
    if (!postEl || !postEl.classList.contains('post-read')) return;
    clearReadVisualState(postEl);
    _readObserver.observe(postEl);
}

function applyReadMediaHalfHeight(postEl) {
    if (!postEl) return;
    postEl.querySelectorAll('.post-media.gallery').forEach(gallery => {
        if (gallery.classList.contains('expanded')) return;
        gallery.style.maxHeight = getReadCollapsedGalleryHeight(gallery) + 'px';
    });
    postEl.querySelectorAll('.post-image, .post-video').forEach(media => {
        const container = media.closest('.gallery-item') || media.closest('.post-media') || media.closest('.video-container') || media.parentElement;

        const apply = () => {
            if (!postEl.classList.contains('post-read')) return;
            if (container) {
                container.style.width = '';
                container.style.height = '';
                container.style.overflow = '';
                delete container.dataset.wasResized;
            }
            const measured = media.getBoundingClientRect().height;
            if (!media.dataset.readBaseHeight && measured > 1) {
                media.dataset.readBaseHeight = String(measured);
            }
            const baseHeight = parseFloat(media.dataset.readBaseHeight);
            if (!baseHeight || baseHeight < 2) return;
            media.style.maxHeight = 'none';
            media.style.height = Math.round(baseHeight / 2) + 'px';
            media.style.width = 'auto';
            media.dataset.readScaled = 'true';

            if (media.classList && media.classList.contains('post-video') && container) {
                container.style.height = media.style.height;
                container.style.width = 'fit-content';
                container.style.marginLeft = 'auto';
                container.style.marginRight = 'auto';
            }
        };

        if (media instanceof HTMLImageElement && !media.complete) {
            media.addEventListener('load', () => requestAnimationFrame(apply), { once: true });
            return;
        }
        if (media instanceof HTMLVideoElement && media.readyState < 1) {
            media.addEventListener('loadedmetadata', () => requestAnimationFrame(apply), { once: true });
            return;
        }
        requestAnimationFrame(apply);
    });
}

// Interacted posts that haven't scrolled out yet (pending dimming)
const _interactedPostIds = getReadPosts(); // seed from storage

// IntersectionObserver: when an interacted post leaves the viewport, dim it
const _readObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        const post = entry.target;
        const id = post.dataset.postId;
        if (!id) return;
        if (!entry.isIntersecting && _interactedPostIds.has(id)) {
            post.classList.add('post-read');
            applyReadMediaHalfHeight(post);
            if (typeof VideoManager !== 'undefined') VideoManager.updatePlayback();
        }
    });
}, { threshold: 0 });

function markPostRead(postEl) {
    if (!isFeatureEnabled('readDimming')) return;
    const id = postEl?.dataset?.postId;
    if (!id) return;
    undimPostUntilExit(postEl);
    _interactedPostIds.add(id);
    const readSet = getReadPosts();
    readSet.add(id);
    saveReadPosts(readSet);
    // Start observing so dimming happens once it scrolls out
    _readObserver.observe(postEl);
}
function restoreReadState(root) {
    if (!isFeatureEnabled('readDimming')) return;
    const readSet = getReadPosts();
    if (!readSet.size) return;
    (root || document).querySelectorAll('.post').forEach(post => {
        if (readSet.has(post.dataset.postId)) {
            // Interacted in a previous load — dim immediately + observe
            post.classList.add('post-read');
            applyReadMediaHalfHeight(post);
            _readObserver.observe(post);
        }
    });
}
// Expose globally so posts.js can call it
window.markPostRead = markPostRead;
window.restoreReadState = restoreReadState;

// Interacting with a dimmed post undims it until it leaves the viewport again.
document.addEventListener('pointerdown', (event) => {
    if (!isFeatureEnabled('readDimming')) return;
    const post = event.target.closest('.post.post-read');
    if (!post) return;
    undimPostUntilExit(post);
}, true);

document.addEventListener('focusin', (event) => {
    if (!isFeatureEnabled('readDimming')) return;
    const post = event.target.closest('.post.post-read');
    if (!post) return;
    undimPostUntilExit(post);
}, true);

// ── Feature: Favorites ──
// Click the heart icon (desktop) or double-tap (mobile) to toggle favorite.
// Stored in localStorage (persists across sessions).
function getFavorites() {
    try { return new Set(JSON.parse(localStorage.getItem('favorites') || '[]')); }
    catch { return new Set(); }
}
function saveFavorites(set) {
    try { localStorage.setItem('favorites', JSON.stringify([...set])); } catch {}
}
function showHeartAnimation(postEl) {
    const heart = document.createElement('div');
    heart.className = 'heart-burst';
    heart.textContent = '❤️';
    postEl.appendChild(heart);
    heart.addEventListener('animationend', () => heart.remove());
}
function toggleFavorite(post) {
    if (!isFeatureEnabled('favorites')) return;
    const postId = post.dataset.postId;
    if (!postId) return;
    const icon = post.querySelector('.favorite-icon');
    const favs = getFavorites();
    if (favs.has(postId)) {
        // Unfavorite
        favs.delete(postId);
        saveFavorites(favs);
        if (icon) { icon.classList.remove('favorited'); icon.textContent = '♡'; icon.title = 'Favorite'; }
        showHeartAnimation(post);
    } else {
        // Favorite
        favs.add(postId);
        saveFavorites(favs);
        if (icon) { icon.classList.add('favorited'); icon.textContent = '❤️'; icon.title = 'Unfavorite'; }
        showHeartAnimation(post);
        markPostRead(post);
    }
}
// Ensure every post has a heart icon (outline by default)
function ensureHeartIcons(root) {
    if (!isFeatureEnabled('favorites')) return;
    (root || document).querySelectorAll('.post').forEach(post => {
        if (post.querySelector('.favorite-icon')) return;
        const metaLeft = post.querySelector('.post-meta-left');
        if (!metaLeft) return;
        const icon = document.createElement('span');
        icon.className = 'favorite-icon';
        icon.title = 'Favorite';
        icon.textContent = '♡';
        metaLeft.insertBefore(icon, metaLeft.firstChild);
    });
}
function restoreFavorites(root) {
    if (!isFeatureEnabled('favorites')) return;
    ensureHeartIcons(root);
    const favs = getFavorites();
    if (!favs.size) return;
    (root || document).querySelectorAll('.post').forEach(post => {
        if (favs.has(post.dataset.postId)) {
            const icon = post.querySelector('.favorite-icon');
            if (icon) { icon.classList.add('favorited'); icon.textContent = '❤️'; icon.title = 'Unfavorite'; }
        }
    });
}
window.restoreFavorites = restoreFavorites;

// Desktop: click on the heart icon to toggle favorite
document.addEventListener('click', (e) => {
    const icon = e.target.closest('.favorite-icon');
    if (!icon) return;
    e.stopPropagation();
    const post = icon.closest('.post');
    if (post) toggleFavorite(post);
}, true);

// Mobile: double-tap anywhere on the post to toggle favorite
const isTouchDevice = 'ontouchstart' in window || navigator.maxTouchPoints > 0;
if (isTouchDevice) {
    document.addEventListener('dblclick', (e) => {
        const post = e.target.closest('.post');
        if (!post) return;
        if (e.target.closest('a, button, input, select, video, audio, .video-controls, .comment')) return;
        toggleFavorite(post);
    });
}

// ── Feature: Keyboard Navigation ──
// J/K = next/prev post, Space = toggle comments, P = toggle pin, Esc = close
let kbFocusIndex = -1;

function getAllPosts() {
    return document.querySelectorAll('.post');
}

function findFirstVisiblePostIndex() {
    const posts = getAllPosts();
    for (let i = 0; i < posts.length; i++) {
        const rect = posts[i].getBoundingClientRect();
        // Post is visible if its bottom is below the top of the viewport
        // and its top is at most 60% down the viewport
        if (rect.bottom > 0 && rect.top < window.innerHeight * 0.6) return i;
    }
    return 0;
}

function focusPost(index) {
    const posts = getAllPosts();
    if (posts.length === 0) return;
    // Clamp
    index = Math.max(0, Math.min(index, posts.length - 1));
    // Remove previous focus
    const prev = document.querySelector('.post-focused');
    if (prev) prev.classList.remove('post-focused');
    // Apply new focus
    const post = posts[index];
    post.classList.add('post-focused');
    // Scroll the post to a few px above the top of the viewport
    const targetY = post.getBoundingClientRect().top + window.scrollY - 12;
    window.scrollTo({ top: targetY, behavior: 'smooth' });
    kbFocusIndex = index;
}

function getFocusedPost() {
    return document.querySelector('.post-focused');
}

document.addEventListener('keydown', (e) => {
    if (!isFeatureEnabled('keyboardNav')) return;
    // Don't hijack when typing in inputs
    if (e.target.matches('input, textarea, select, [contenteditable]')) return;

    const key = e.key.toLowerCase();

    if (key === 'j') {
        // Next post (start from currently visible if no focus yet)
        if (kbFocusIndex < 0) kbFocusIndex = findFirstVisiblePostIndex() - 1;
        focusPost(kbFocusIndex + 1);
        e.preventDefault();
    } else if (key === 'k') {
        // Previous post (start from currently visible if no focus yet)
        if (kbFocusIndex < 0) kbFocusIndex = findFirstVisiblePostIndex() + 1;
        focusPost(kbFocusIndex - 1);
        e.preventDefault();
    } else if (key === ' ') {
        // Space = toggle comments on focused post
        const post = getFocusedPost();
        if (!post) return;
        e.preventDefault();
        post.click(); // triggers the existing post click handler
    } else if (key === 'p') {
        // Toggle pin on focused post
        const post = getFocusedPost();
        if (!post) return;
        e.preventDefault();
        const pinForm = post.querySelector('.inline-form');
        if (pinForm) {
            pinForm.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
        }
    } else if (key === 'escape') {
        const post = getFocusedPost();
        if (post) {
            // First: close comments if open
            const comments = post.querySelector('.post-top-comments');
            if (comments && !comments.hidden) {
                comments.hidden = true;
                return;
            }
        }
        // Then: collapse expanded galleries (existing handler also fires)
        // Finally: clear focus
        if (post) {
            post.classList.remove('post-focused');
            kbFocusIndex = -1;
        }
    }
});

// ── Restore state on load and after infinite scroll ──
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        restoreReadState(document);
        restoreFavorites(document);
    });
} else {
    restoreReadState(document);
    restoreFavorites(document);
}
document.addEventListener('newPostsAdded', (event) => {
    const root = event.detail?.container || document;
    restoreReadState(root);
    restoreFavorites(root);
});

// Global Video Manager to ensure only one video plays at a time (the most visible one)
const VideoManager = {
    videos: new Map(), // videoContainer -> intersectionRatio
    observer: null,

    isAutoplayEligible(container) {
        const post = container?.closest('.post');
        return !(post && post.classList.contains('post-read'));
    },
    
    init() {
        if (this.observer) return;
        this.observer = new IntersectionObserver(this.handleIntersect.bind(this), {
            threshold: [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
        });
    },
    
    register(container) {
        this.init();
        this.observer.observe(container);
        this.videos.set(container, 0);
    },
    
    handleIntersect(entries) {
        entries.forEach(entry => {
            // Update visibility ratio
            this.videos.set(entry.target, entry.intersectionRatio);
            // If a container leaves the viewport, clear any manual pause
            if (!entry.isIntersecting) {
                delete entry.target.dataset.manualPaused;
            }
        });
        this.updatePlayback();
    },
    
    updatePlayback() {
        let bestContainer = null;
        let maxRatio = 0;
        
        for (const [container, ratio] of this.videos.entries()) {
            if (!this.isAutoplayEligible(container)) continue;
            if (ratio > maxRatio) {
                maxRatio = ratio;
                bestContainer = container;
            }
        }
        
        // Only play if visibility is significant (e.g. > 40%)
        if (bestContainer && maxRatio > 0.4) {
            // Called from intersection observer -> this is autoplay-driven
            this.playOnly(bestContainer, true);
        } else {
            this.pauseAll();
        }
    },
    
    playOnly(targetContainer, isAutoplay = false) {
        if (isAutoplay && targetContainer && !this.isAutoplayEligible(targetContainer)) {
            targetContainer = null;
        }

        // If the target container was manually paused by the user, try to find
        // another visible container that is not manually paused. If none,
        // keep everything paused.
        if (targetContainer && targetContainer.dataset.manualPaused === 'true') {
            // find next best container (visible and not manually paused)
            let fallback = null;
            let bestRatio = 0;
            for (const [container, ratio] of this.videos.entries()) {
                if (isAutoplay && !this.isAutoplayEligible(container)) continue;
                if (container.dataset.manualPaused === 'true') continue;
                if (ratio > bestRatio && ratio > 0.4) {
                    bestRatio = ratio;
                    fallback = container;
                }
            }
            if (!fallback) {
                // No eligible container to autoplay — pause all
                this.pauseAll();
                return;
            }
            targetContainer = fallback;
        }

        for (const [container] of this.videos.entries()) {
            const video = container.querySelector('.post-video');
            const audio = container.querySelector('.video-audio');
            const playBtn = container.querySelector('.video-play-pause');

            if (container === targetContainer) {
                if (video.paused) {
                    // If this playback is triggered by autoplay, ensure it starts muted
                    if (isAutoplay) {
                            try {
                                video.muted = true;
                                video.volume = 0;
                                if (audio) {
                                    audio.muted = true;
                                    audio.volume = 0;
                                }
                                // Update UI controls if present
                                const volSlider = container.querySelector('.video-volume-slider');
                                const muteBtn = container.querySelector('.video-mute');
                                if (volSlider) volSlider.value = 0;
                                if (muteBtn) muteBtn.textContent = '🔇';
                                // Ensure the next user click is treated as first click (unmute)
                                container.dataset.firstClick = 'true';
                            } catch (e) {}
                    }

                    video.play().catch(() => {});
                    if (audio && !audio.muted && audio.volume > 0) {
                        audio.currentTime = video.currentTime;
                        audio.play().catch(() => {});
                    }
                    if (playBtn) playBtn.textContent = '⏸';
                }
            } else {
                if (!video.paused) {
                    video.pause();
                    if (audio) audio.pause();
                    if (playBtn) playBtn.textContent = '▶';
                }
            }
        }
    },
    
    pauseAll() {
        for (const [container] of this.videos.entries()) {
            const video = container.querySelector('.post-video');
            const audio = container.querySelector('.video-audio');
            const playBtn = container.querySelector('.video-play-pause');
            
            if (!video.paused) {
                video.pause();
                if (audio) audio.pause();
                if (playBtn) playBtn.textContent = '▶';
            }
        }
    }
};

// Video controls initialization function
function initVideoControls(rootElement) {
    rootElement.querySelectorAll('.video-container').forEach(container => {
        // Skip if already initialized
        if (container.dataset.videoInitialized) return;
        container.dataset.videoInitialized = 'true';
        const video = container.querySelector('.post-video');
        let audio = container.querySelector('.video-audio');
        const playPauseBtn = container.querySelector('.video-play-pause');
        const timeline = container.querySelector('.video-timeline');
        const progress = container.querySelector('.video-progress');
        const muteBtn = container.querySelector('.video-mute');
        const volumeSlider = container.querySelector('.video-volume-slider');
        const speedDecreaseBtn = container.querySelector('.video-speed-decrease');
        const speedIncreaseBtn = container.querySelector('.video-speed-increase');
        const speedDisplay = container.querySelector('.video-speed-display');
        const fullscreenBtn = container.querySelector('.video-fullscreen');
        
        let hls = null;
        let audioLoaded = false;

        // Get HLS URL from data attribute (has audio built-in)
        const hlsUrl = container.dataset.hlsUrl;
        const audioUrl = container.dataset.audioUrl;
        
        // Try HLS first - it has audio included
        if (hlsUrl && Hls.isSupported()) {
            hls = new Hls();
            hls.loadSource(hlsUrl);
            hls.attachMedia(video);
            hls.on(Hls.Events.MANIFEST_PARSED, () => {
                video.play().catch(() => {});
            });
            audioLoaded = true; // HLS has audio built-in
        } else if (hlsUrl && video.canPlayType('application/vnd.apple.mpegurl')) {
            // Safari native HLS support
            video.src = hlsUrl;
            audioLoaded = true;
        }

        // Initialize video - default muted (no sound)
        video.muted = true;
        video.volume = 0;
        
        // Initialize audio element for synced playback (fallback when no HLS)
        // If no audio element exists but we have an audioUrl, create one
        if (!audio && audioUrl && !audioLoaded) {
            audio = document.createElement('audio');
            audio.src = audioUrl;
            audio.style.display = 'none';
            audio.loop = true;
            audio.muted = true;
            container.appendChild(audio);
        }
        
        if (audio && !audioLoaded) {
            audio.volume = 0;
            audio.muted = true;
            
            // Try to load audio, with fallback to 64kbps if 128 fails
            audio.addEventListener('error', () => {
                if (audio.src.includes('DASH_AUDIO_128')) {
                    audio.src = audio.src.replace('DASH_AUDIO_128', 'DASH_AUDIO_64');
                    audio.load();
                }
            }, { once: true });
            
            audio.load();
            
            // Sync audio with video
            video.addEventListener('play', () => {
                audio.currentTime = video.currentTime;
                if (!audio.muted && audio.volume > 0) {
                    audio.play().catch(() => {});
                }
            });
            video.addEventListener('pause', () => audio.pause());
            video.addEventListener('seeked', () => {
                audio.currentTime = video.currentTime;
            });
            
            // Keep audio synced during playback
            video.addEventListener('timeupdate', () => {
                if (Math.abs(video.currentTime - audio.currentTime) > 0.3) {
                    audio.currentTime = video.currentTime;
                }
            });
        }
        
        // Update volume slider to 0
        volumeSlider.value = 0;
        muteBtn.textContent = '🔇';

        // Play/Pause (optional button) - only wire if the button exists
        if (playPauseBtn) {
            playPauseBtn.addEventListener('click', () => {
                if (video.paused) {
                    // User explicitly requested play -> clear manual pause flag
                    delete container.dataset.manualPaused;
                    VideoManager.playOnly(container);
                } else {
                    // User explicitly paused -> mark as manually paused
                    video.pause();
                    if (audio) audio.pause();
                    container.dataset.manualPaused = 'true';
                    playPauseBtn.textContent = '▶';
                }
            });
        }

        // Track if first click should unmute (per-container)
        // Use dataset so autoplay can reset this flag when needed
        container.dataset.firstClick = 'true';
        const userDefaultVolume = window.defaultVolume || 0.05;
        const userDefaultSpeed = window.defaultSpeed || 1.0;
        
        // Set default playback speed
        video.playbackRate = userDefaultSpeed;
        if (speedDisplay) speedDisplay.textContent = userDefaultSpeed + 'x';

        // Video click - first click unmutes to default volume, subsequent clicks toggle play/pause
        video.addEventListener('click', (e) => {
            // Prevent clicks on media from toggling comments
            e.stopPropagation();
            // Ignore click that fires after a drag-resize
            if (window.__didMediaResize) {
                window.__didMediaResize = false;
                return;
            }
            // First click unmutes to user's default volume
            if (container.dataset.firstClick === 'true' && (video.muted || video.volume === 0)) {
                container.dataset.firstClick = 'false';
                video.muted = false;
                video.volume = userDefaultVolume;
                if (audio) {
                    audio.muted = false;
                    audio.volume = userDefaultVolume;
                    audio.currentTime = video.currentTime;
                    if (!video.paused) {
                        audio.play().catch(() => {});
                    }
                }
                volumeSlider.value = userDefaultVolume * 100;
                muteBtn.textContent = userDefaultVolume > 0.5 ? '🔊' : '🔉';
                return; // Don't toggle pause on first click
            }

            container.dataset.firstClick = 'false';
            
            // Pause all other videos
            document.querySelectorAll('.post-video').forEach(v => {
                if (v !== video) {
                    v.pause();
                    const vAudioEl = v.closest('.video-container').querySelector('.video-audio');
                    if (vAudioEl) vAudioEl.pause();
                    const otherBtn = v.closest('.video-container').querySelector('.video-play-pause');
                    if (otherBtn) otherBtn.textContent = '▶';
                }
            });
            
            // Toggle play/pause (user action)
            if (video.paused) {
                // User resumed playback -> clear manual pause flag
                delete container.dataset.manualPaused;
                VideoManager.playOnly(container);
                if (playPauseBtn) playPauseBtn.textContent = '⏸';
            } else {
                // User paused playback -> set manual pause flag
                video.pause();
                if (audio) audio.pause();
                container.dataset.manualPaused = 'true';
                if (playPauseBtn) playPauseBtn.textContent = '▶';
            }
        });

        // Timeline - click and drag support
        let isDragging = false;
        
        const updateVideoTime = (e) => {
            const rect = timeline.getBoundingClientRect();
            const percent = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
            video.currentTime = percent * video.duration;
            // Update progress bar immediately while dragging
            progress.style.width = (percent * 100) + '%';
        };
        
        timeline.addEventListener('mousedown', (e) => {
            isDragging = true;
            updateVideoTime(e);
        });
        
        document.addEventListener('mousemove', (e) => {
            if (isDragging) {
                updateVideoTime(e);
            }
        });
        
        document.addEventListener('mouseup', () => {
            isDragging = false;
        });
        
        timeline.addEventListener('click', (e) => {
            updateVideoTime(e);
        });

        // Update progress
        video.addEventListener('timeupdate', () => {
            if (!isDragging) {
                const percent = (video.currentTime / video.duration) * 100;
                progress.style.width = percent + '%';
            }
        });

        // Mute button: toggle mute and open/close volume popover
        muteBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            video.muted = !video.muted;
            if (audio) audio.muted = video.muted;
            if (video.muted) {
                muteBtn.textContent = '🔇';
            } else {
                muteBtn.textContent = video.volume > 0.5 ? '🔊' : '🔉';
                if (video.volume === 0) {
                    video.volume = 0.05;
                    if (audio) audio.volume = 0.05;
                    volumeSlider.value = 5;
                }
            }

            // Toggle visible slider; auto-hide after a few seconds
            container.classList.toggle('volume-open');
            if (container._volumeTimeout) {
                clearTimeout(container._volumeTimeout);
                container._volumeTimeout = null;
            }
            container._volumeTimeout = setTimeout(() => {
                container.classList.remove('volume-open');
                container._volumeTimeout = null;
            }, 3500);
        });

        // Volume slider
        volumeSlider.addEventListener('input', (e) => {
            const volume = parseInt(e.target.value) / 100;
            video.volume = volume;
            if (audio) {
                audio.volume = volume;
                audio.muted = false;
                // If audio is available and volume > 0, try to play it
                if (volume > 0 && audio.paused && !video.paused) {
                    audio.currentTime = video.currentTime;
                    audio.play().catch(() => {});
                }
            }
            video.muted = volume === 0;
            if (volume === 0) {
                muteBtn.textContent = '🔇';
                if (audio) audio.pause();
            } else {
                muteBtn.textContent = volume > 0.5 ? '🔊' : '🔉';
            }
        });

        // Keep slider visible while interacting with it
        volumeSlider.addEventListener('pointerdown', (e) => {
            e.stopPropagation();
            container.classList.add('volume-open');
            if (container._volumeTimeout) { clearTimeout(container._volumeTimeout); container._volumeTimeout = null; }
        });
        volumeSlider.addEventListener('pointerup', (e) => {
            e.stopPropagation();
            if (container._volumeTimeout) clearTimeout(container._volumeTimeout);
            container._volumeTimeout = setTimeout(() => { container.classList.remove('volume-open'); container._volumeTimeout = null; }, 1200);
        });
        volumeSlider.addEventListener('blur', () => {
            if (container._volumeTimeout) clearTimeout(container._volumeTimeout);
            container._volumeTimeout = setTimeout(() => { container.classList.remove('volume-open'); container._volumeTimeout = null; }, 400);
        });

        // Playback speed +/- buttons
        const changeSpeed = (delta) => {
            let newSpeed = Math.round((video.playbackRate + delta) * 100) / 100;
            if (newSpeed < 0.25) newSpeed = 0.25;
            if (newSpeed > 2) newSpeed = 2;
            video.playbackRate = newSpeed;
            if (audio) audio.playbackRate = newSpeed;

            // Show temporary popup above the +/- buttons with the new speed
            if (speedDisplay) {
                speedDisplay.textContent = newSpeed + 'x';
                speedDisplay.classList.add('show');
                if (container._speedTimeout) {
                    clearTimeout(container._speedTimeout);
                    container._speedTimeout = null;
                }
                container._speedTimeout = setTimeout(() => {
                    speedDisplay.classList.remove('show');
                    container._speedTimeout = null;
                }, 900);
            }
        };

        if (speedDecreaseBtn) speedDecreaseBtn.addEventListener('click', (e) => { e.stopPropagation(); changeSpeed(-0.25); });
        if (speedIncreaseBtn) speedIncreaseBtn.addEventListener('click', (e) => { e.stopPropagation(); changeSpeed(0.25); });

        // Fullscreen
        fullscreenBtn.addEventListener('click', () => {
            if (document.fullscreenElement) {
                document.exitFullscreen();
            } else {
                container.requestFullscreen().catch(() => {
                    // Fallback for older browsers
                    if (container.webkitRequestFullscreen) {
                        container.webkitRequestFullscreen();
                    } else if (container.mozRequestFullScreen) {
                        container.mozRequestFullScreen();
                    }
                });
            }
        });

        // CTRL+Scroll for volume
        container.addEventListener('wheel', (e) => {
            if (e.ctrlKey) {
                e.preventDefault();
                const delta = e.deltaY > 0 ? -5 : 5;
                const newVolume = Math.max(0, Math.min(100, parseInt(volumeSlider.value) + delta));
                volumeSlider.value = newVolume;
                video.volume = newVolume / 100;
                video.muted = newVolume === 0;
                muteBtn.textContent = newVolume === 0 ? '🔇' : (newVolume > 50 ? '🔊' : '🔉');
            }
        }, { passive: false });

        // Register with global manager for auto-play logic
        VideoManager.register(container);
    });
}

// Media resizer: allow click-and-drag resizing anywhere on media elements
function initMediaResizers(rootElement) {
    rootElement.querySelectorAll('.post-media, .post-image, .post-video, .gallery-image, .comment-body img, .comment-body video').forEach(el => {
        // Determine the clickable/draggable target: prefer image or video element
        const target = el.classList && el.classList.contains('post-media') ? (el.querySelector('img') || el.querySelector('video')) : el;
        if (!target) return;

        const primeReadBaseHeight = () => {
            if (target.dataset.readBaseHeight) return;
            const h = target.getBoundingClientRect().height;
            if (h && h > 1) target.dataset.readBaseHeight = String(h);
        };
        if (target instanceof HTMLImageElement && !target.complete) {
            target.addEventListener('load', () => requestAnimationFrame(primeReadBaseHeight), { once: true });
        } else if (target instanceof HTMLVideoElement && target.readyState < 1) {
            target.addEventListener('loadedmetadata', () => requestAnimationFrame(primeReadBaseHeight), { once: true });
        } else {
            requestAnimationFrame(primeReadBaseHeight);
        }

        // For gallery images, use the .gallery-item wrapper so each image resizes independently
        let container = null;
        if (target.closest && target.closest('.gallery-item')) {
            container = target.closest('.gallery-item');
        }
        if (!container) {
            container = target.closest('.post-media') || target.closest('.video-container') || target.parentElement;
        }
        if (!container || container.dataset.resizeInit) return;
        container.dataset.resizeInit = 'true';

        // Do not lift CSS caps on init. Ensure default rendering fits container.
        // Skip for gallery images — their CSS width (50%) should be preserved.
        const isGalleryImage = target.classList && target.classList.contains('gallery-image');
        if (!container.dataset.wasResized && !isGalleryImage) {
            try {
                // Keep default media sizing on init; read-state sizing is applied separately.
                target.style.maxHeight = '';
                target.style.width = '100%';
                target.style.height = 'auto';
                container.style.width = '';
                container.style.height = '';
            } catch (e) {}
        }

        let isResizing = false;
        let isMouseDown = false;
        let downX = 0;
        let downY = 0;
        const resizeDragThreshold = 6;
        let startX = 0;
        let startY = 0;
        let startWidth = 0;
        let startHeight = 0;
        let naturalW = 0;
        let naturalH = 0;
        let availableMaxWidth = null;

        const getNatural = () => {
            const nw = target.naturalWidth || target.videoWidth || target.clientWidth;
            const nh = target.naturalHeight || target.videoHeight || target.clientHeight;
            return { nw, nh };
        };

        const startResize = (e) => {
            if (isResizing) return;
            isResizing = true;
            startX = downX;
            startY = downY;
            e.preventDefault();
            e.stopPropagation();
            // For gallery images, use the target (img) rect so startWidth matches
            // the rendered image size, not the full-width .gallery-item container.
            const sizeEl = isGalleryImage ? target : container;
            const rect = sizeEl.getBoundingClientRect();
            startWidth = rect.width;
            startHeight = rect.height || target.getBoundingClientRect().height;
            const nat = getNatural();
            naturalW = nat.nw || startWidth;
            naturalH = nat.nh || startHeight;
            // Compute a stable cap based on the bounding post container
            const boundingAncestor = container.closest('.comment') || container.closest('.post') || container.closest('.post-detail') || container.closest('.main-content') || document.body;
            const bRect = boundingAncestor.getBoundingClientRect();
            const bStyle = window.getComputedStyle(boundingAncestor);
            const padLeft = parseFloat(bStyle.paddingLeft) || 0;
            const padRight = parseFloat(bStyle.paddingRight) || 0;
            availableMaxWidth = Math.max(100, Math.round(bRect.width - padLeft - padRight - 20));
            try {
                container.style.boxSizing = 'border-box';
                target.style.maxWidth = availableMaxWidth + 'px';
                target.style.maxHeight = 'none';
                container.style.overflow = 'hidden';
            } catch (e) {}
            document.body.style.cursor = 'nwse-resize';
        };

        const onMouseDown = (e) => {
            if (e.button !== 0) return;
            if (e.target.closest('.video-controls') || e.target.closest('button') || e.target.closest('input')) return;
            isMouseDown = true;
            downX = e.clientX;
            downY = e.clientY;
        };

        const onMouseMove = (e) => {
            if (!isMouseDown) return;
            if (!isResizing) {
                const deltaX = e.clientX - downX;
                const deltaY = e.clientY - downY;
                if (Math.hypot(deltaX, deltaY) < resizeDragThreshold) return;
                startResize(e);
            }
            if (!isResizing) return;
            const dx = e.clientX - startX;
            const dy = e.clientY - startY;

            const nat = getNatural();
            const nw = nat.nw || naturalW || startWidth;
            const nh = nat.nh || naturalH || startHeight;
            const maxAllowedWidth = availableMaxWidth || (container.closest('.post') || document.body).getBoundingClientRect().width - 20;
            const maxAllowedHeight = (nw && nh && maxAllowedWidth) ? Math.max(50, Math.round(maxAllowedWidth * (nh / nw))) : null;

            if (Math.abs(dy) > Math.abs(dx)) {
                let desiredHeight = Math.max(50, Math.round(startHeight + dy));
                let scale = nh ? desiredHeight / nh : desiredHeight / startHeight;
                let newWidth = Math.max(50, Math.round(nw * scale));
                if (newWidth > maxAllowedWidth) {
                    newWidth = maxAllowedWidth;
                    scale = nw ? (newWidth / nw) : (desiredHeight / startHeight);
                    desiredHeight = Math.max(50, Math.round(nh * scale));
                    if (maxAllowedHeight) desiredHeight = Math.min(desiredHeight, maxAllowedHeight);
                }
                container.style.width = newWidth + 'px';
                container.style.height = desiredHeight + 'px';
                target.style.width = newWidth + 'px';
                target.style.height = desiredHeight + 'px';
            } else {
                const desiredWidthRaw = Math.max(50, Math.round(startWidth + dx));
                const desiredWidth = Math.min(desiredWidthRaw, maxAllowedWidth);
                const scale = nw ? desiredWidth / nw : desiredWidth / startWidth;
                let newHeight = Math.max(50, Math.round(nh * scale));
                if (desiredWidth >= maxAllowedWidth && maxAllowedHeight) {
                    newHeight = Math.min(newHeight, maxAllowedHeight);
                }
                container.style.width = desiredWidth + 'px';
                container.style.height = newHeight + 'px';
                target.style.width = desiredWidth + 'px';
                target.style.height = newHeight + 'px';
            }

            container.dataset.wasResized = 'true';
        };

        const onMouseUp = (e) => {
            if (!isMouseDown && !isResizing) return;
            isMouseDown = false;
            if (!isResizing) return;
            isResizing = false;
            document.body.style.cursor = '';
            const rect = container.getBoundingClientRect();
            const sizeChanged = Math.abs(rect.width - startWidth) > 2 || Math.abs(rect.height - startHeight) > 2;
            if (!sizeChanged) {
                try {
                    target.style.maxWidth = '';
                    target.style.maxHeight = '';
                    target.style.width = '';
                    target.style.height = '';
                    container.style.width = '';
                    container.style.height = '';
                    container.style.overflow = '';
                } catch (err) {}
            } else {
                container.dataset.wasResized = 'true';
                // Signal handlers to ignore the next click after a resize
                const gallery = container.closest('.gallery');
                if (gallery) gallery.dataset.didResize = 'true';
                window.__didMediaResize = true;
                // Mark post as read after resizing media
                const post = container.closest('.post');
                if (post && window.markPostRead) window.markPostRead(post);
            }
        };

        target.addEventListener('mousedown', onMouseDown);
        target.addEventListener('dragstart', (e) => { e.preventDefault(); });
        document.addEventListener('mousemove', onMouseMove);
        document.addEventListener('mouseup', onMouseUp);

        // Stop propagation for media clicks to prevent toggling comments
        target.addEventListener('click', (e) => {
            e.stopPropagation();
        });
    });
}
