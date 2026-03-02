(function() {
    const container = document.getElementById('posts-container');
    if (!container) return;
    // Attach copy-to-clipboard handler for share buttons (works for server and client rendered posts)
    function setupShareButtons(root=document) {
        const shareBtns = root.querySelectorAll('.share-btn');
        shareBtns.forEach(btn => {
            if (btn._shareHandlerAttached) return;
            btn._shareHandlerAttached = true;
            btn.addEventListener('click', async (e) => {
                // Only intercept primary (left) clicks without modifier keys — allow middle-click/new-tab
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
                    setTimeout(() => { btn.textContent = original; btn.disabled = false; }, 1500);
                } catch (err) {
                    console.error('Copy failed', err);
                }
            });
        });
    }

    // initial setup (for server rendered buttons)
    setupShareButtons(document);

    // observe for dynamically added posts (client-side rendering)
    const observer = new MutationObserver((mutations) => {
        for (const m of mutations) {
            if (m.addedNodes && m.addedNodes.length) setupShareButtons(m.target);
        }
    });
    observer.observe(container, { childList: true, subtree: true });

    const subreddit = container.dataset.subreddit;
    const sort = container.dataset.sort;
    const timeFilter = container.dataset.timeFilter || 'day';
    const commentsLimit = container.dataset.commentsLimit;
    const isAuthenticated = container.dataset.isAuthenticated === 'true';
    let pinnedSubs = JSON.parse(container.dataset.pinnedSubs || '[]');
    let feedPinnedSubs = JSON.parse(container.dataset.feedPinnedSubs || '[]');
    const titleLinks = container.dataset.titleLinks === 'true';
    let after = container.dataset.after;
    let loading = false;
    let noMorePosts = false;
    let postCount = document.querySelectorAll('.post').length;
    
    const loadingIndicator = document.getElementById('loading-indicator');
    const noMoreIndicator = document.getElementById('no-more-posts');

    // Update the top pinned-subreddits navigation when pins change
    function refreshPinnedNav() {
        const nav = document.querySelector('.subreddit-nav');
        if (!nav) return;

        if (isAuthenticated && Array.isArray(pinnedSubs) && pinnedSubs.length) {
            let html = '';
            pinnedSubs.forEach(sub => {
                const active = (sub === subreddit) ? ' active' : '';
                html += `<a href="/r/${encodeURIComponent(sub)}" class="subreddit-link${active}">r/${escapeHTML(sub)}</a>`;
            });
            if (!pinnedSubs.includes(subreddit)) {
                html += `<span class="subreddit-link active">r/${escapeHTML(subreddit)}</span>`;
            }
            nav.innerHTML = html;
        } else {
            // fallback to default nav
            let html = `<a href="/r/all" class="subreddit-link ${subreddit === 'all' ? 'active' : ''}">r/all</a>`;
            html += `<a href="/r/popular" class="subreddit-link ${subreddit === 'popular' ? 'active' : ''}">r/popular</a>`;
            if (subreddit && !['all', 'popular'].includes(subreddit)) html += `<span class="subreddit-link active">r/${escapeHTML(subreddit)}</span>`;
            nav.innerHTML = html;
        }
    }
    
    // Create post HTML from post data
    // escapeHTML is defined globally in base.html

    function createPostHTML(post, index) {
        // Escape title/author/subreddit/permalink/url for safe insertion
        const safeTitle = escapeHTML(post.title || '');
        const safeAuthor = escapeHTML(post.author || '');
        const safeSub = escapeHTML(post.subreddit || '');
        const safePermalink = escapeHTML(post.permalink || '');
        const safeUrl = escapeHTML(post.url || '');

        // Simple HTML escape and newline to br for selftext
        const selftextRaw = post.selftext || '';
        const selftext = escapeHTML(selftextRaw).replace(/\n/g, '<br>');

        const score = post.score.toLocaleString();
        const numComments = post.num_comments.toLocaleString();
        
        let mediaHTML = '';
        
        if (post.is_video && (post.hls_url || post.video_url)) {
            mediaHTML = `
                <div class="post-media video-container" data-hls-url="${post.hls_url || ''}" data-audio-url="${post.audio_url || ''}">
                    <video class="post-video" src="${post.video_url}" loop playsinline autoplay muted></video>
                    ${post.audio_url ? `<audio class="video-audio" src="${post.audio_url}" style="display:none;" loop muted></audio>` : ''}
                    <div class="video-controls">
                        
                        <div class="video-timeline"><div class="video-progress"></div></div>
                        <div class="video-volume-container">
                            <button class="video-btn video-mute" aria-label="Mute">🔇</button>
                            <input type="range" class="video-volume-slider" min="0" max="100" value="0">
                        </div>
                        <div class="video-speed-container">
                            <button class="video-btn video-speed-decrease" aria-label="Decrease speed">−</button>
                            <div class="video-speed-display">1x</div>
                            <button class="video-btn video-speed-increase" aria-label="Increase speed">+</button>
                        </div>
                        <button class="video-btn video-fullscreen" aria-label="Fullscreen">⛶</button>
                    </div>
                </div>`;
        } else if (post.gallery_urls && post.gallery_urls.length > 0) {
            const previewMain = post.gallery_urls[0];
            const previewPeek = post.gallery_urls.length > 1 ? post.gallery_urls[1] : null;
            const galleryItems = post.gallery_urls.map(url => `
                <div class="gallery-item">
                    <img class="gallery-image" src="${url}" alt="Gallery image" loading="lazy">
                </div>
            `).join('');
            mediaHTML = `
                <div class="post-media gallery">
                    <div class="gallery-preview" tabindex="0" role="button" aria-expanded="false">
                        <div class="gallery-preview-main">
                            <img class="gallery-image preview-main" src="${previewMain}" alt="Gallery image" loading="lazy">
                        </div>
                        ${previewPeek ? `
                        <div class="gallery-preview-peek">
                            <img class="gallery-image preview-peek" src="${previewPeek}" alt="Gallery image peek" loading="lazy">
                            ${post.gallery_urls.length > 2 ? `<div class="gallery-more-count">+${post.gallery_urls.length - 1}</div>` : ''}
                        </div>
                        ` : ''}
                    </div>
                    <div class="gallery-scroll gallery-full" hidden>${galleryItems}</div>
                    <!-- navigation buttons removed; preview below main image shows second image -->
                </div>`;
        } else if (post.image_url) {
            mediaHTML = `
                <div class="post-media">
                    <img class="post-image" src="${post.image_url}" alt="Post image">
                </div>`;
        }
        
        const thumbnail = post.thumbnail || post.image_url || '';
        
        return `
            <article class="post" id="post-${index}" data-post-index="${index}" data-thumbnail="${thumbnail}" data-subreddit="${post.subreddit}" data-post-id="${post.id}" data-current-limit="0" data-increment="3" style="cursor: pointer;">
                <div class="post-header">
                    <div class="post-meta-left">
                        <a href="/r/${encodeURIComponent(post.subreddit)}" class="subreddit-link-inline trunc">r/${safeSub}</a>
                        <span class="meta-text post-author trunc">u/${safeAuthor}</span>
                    </div>
                    <div class="post-meta-actions">
                        <span class="meta-text post-upvotes">⬆️${post.score}</span>
                        ${isAuthenticated && feedPinnedSubs.includes(post.subreddit) ? `
                        <form method="post" action="/unpin/${encodeURIComponent(post.subreddit)}" class="inline-form">
                            <input type="hidden" name="csrf_token" value="${window.csrfToken}">
                            <button type="submit" class="meta-action-btn unpin-btn" title="Unpin r/${safeSub}">📍</button>
                        </form>
                        ` : isAuthenticated && !pinnedSubs.includes(post.subreddit) ? `
                        <form method="post" action="/pin/${encodeURIComponent(post.subreddit)}" class="inline-form">
                            <input type="hidden" name="csrf_token" value="${window.csrfToken}">
                            <button type="submit" class="meta-action-btn pin-btn" title="Pin r/${safeSub}">📌</button>
                        </form>
                        ` : ''}
                        ${!post.is_self ? `<a href="${safeUrl}" target="_blank" class="meta-action-btn" title="Open link">🔗</a>` : ''}
                        <a href="/r/${encodeURIComponent(post.subreddit)}/comments/${encodeURIComponent(post.id)}/share" class="meta-action-btn share-btn" data-share-path="/r/${encodeURIComponent(post.subreddit)}/comments/${encodeURIComponent(post.id)}/share" title="Share" rel="noopener noreferrer">🔁</a>
                        <a href="${safePermalink}" target="_blank" class="meta-action-btn" title="View on Reddit">📤</a>
                        ${isAuthenticated && post.subreddit !== subreddit ? `
                        <form method="post" action="/ban/${encodeURIComponent(post.subreddit)}" class="inline-form" onsubmit="return confirm('Ban r/${safeSub}? Posts from this subreddit will be hidden.')">
                            <input type="hidden" name="csrf_token" value="${window.csrfToken}">
                            <button type="submit" class="meta-action-btn ban-btn" title="Ban r/${safeSub}">🚫</button>
                        </form>
                        ` : ''}
                    </div>
                    <button class="meta-menu-toggle" aria-haspopup="true" aria-expanded="false" title="Actions">☰</button>
                    <div class="meta-menu" hidden aria-hidden="true"></div>
                </div>

                <h2 class="post-title">
                        ${titleLinks ? `<a href="/r/${encodeURIComponent(post.subreddit)}/comments/${encodeURIComponent(post.id)}">${safeTitle}</a>` : `<span class="post-title-text">${safeTitle}</span>`}
                </h2>
                
                ${mediaHTML}
                
                ${selftext ? `<div class="post-text-content">${selftext}</div><div class="post-text-toggle" title="Toggle post text" aria-hidden="true"></div>` : ''}
                
                
                <div class="post-top-comments" hidden>
                    <div class="comment-list" data-show-author="false" hidden></div>
                    <div class="load-more-comments-container" hidden style="text-align: center; padding: 10px 0;">
                        <button class="btn load-more-comments-btn">Load 3 more comments</button>
                    </div>
                </div>
            </article>
        `;
    }
    

    // Create comment HTML
    function createCommentHTML(comment, collapsedIds = new Set()) {
        let repliesHTML = '';
        if (comment.replies && comment.replies.length > 0) {
            repliesHTML = `
                <div class="comment-replies">
                    ${comment.replies.map(reply => createCommentHTML(reply, collapsedIds)).join('')}
                </div>
            `;
        }
        
        const isCollapsed = collapsedIds.has(comment.id);
        const collapsedClass = isCollapsed ? 'collapsed' : '';
        const author = comment.author || '[deleted]';
        const displayAuthor = escapeHTML(author);
        const authorHTML = author !== '[deleted]'
            ? `<a href="/u/${encodeURIComponent(author)}" class="comment-author">u/${displayAuthor}</a>`
            : `<span class="comment-author">u/${displayAuthor}</span>`;

        // Use server-provided formatted_body if present (assumed sanitized server-side);
        // otherwise escape raw body text here.
        let bodyHTML = '';
        if (comment.formatted_body) {
            bodyHTML = comment.formatted_body;
        } else {
            bodyHTML = escapeHTML(comment.body || '').replace(/\n/g, '<br>');
        }
        
        // Use regular comment classes to inherit correct styling (blue border, etc.)
        // Added 'comment-reply' class if it's a child (detected by lack of depth property or handle externally? 
        // We'll mimic the structure of comment_tree.html
        return `
            <div class="comment ${comment.depth > 0 ? 'comment-reply' : ''} ${collapsedClass}" data-depth="${comment.depth || 0}" data-comment-id="${comment.id || ''}">
                <div class="comment-content">
                    <div class="comment-meta-right">
                        ${authorHTML}
                        <span class="comment-score">⬆️ ${comment.score.toLocaleString()}</span>
                    </div>
                    <div class="comment-body">${bodyHTML}</div>
                    ${repliesHTML}
                </div>
            </div>
        `;
    }

    // Load top comments for a post
    async function loadTopComments(postElement, limit = 3) {
        const subreddit = postElement.dataset.subreddit;
        const postId = postElement.dataset.postId;
        
        const commentsContainer = postElement.querySelector('.post-top-comments');
        const listContainer = commentsContainer.querySelector('.comment-list');
        const loadMoreContainer = commentsContainer.querySelector('.load-more-comments-container');
        
        // If just expanding and already loaded, do nothing
        if (limit === 3 && postElement.dataset.commentsLoaded === 'true') {
            return;
        }

        try {
            // Find post ID from link if not in dataset
            let pid = postId;
            if (!pid) {
                const link = postElement.querySelector('.post-title a');
                if (link) {
                    // /r/sub/comments/ID/title
                    const parts = link.getAttribute('href').split('/comments/');
                    if (parts.length > 1) {
                        pid = parts[1].split('/')[0];
                    }
                }
            }
            
            if (!pid) return;
            
            // Capture existing collapsed state before loading new comments
            // We only need top-level collapsed IDs, but recursively is fine too
            const collapsedIds = new Set();
            if (listContainer) {
                listContainer.querySelectorAll('.comment.collapsed').forEach(el => {
                    const id = el.dataset.commentId;
                    if (id) collapsedIds.add(id);
                });
            }

            // Show loading indicator only if first load
            if (limit === 3) {
                listContainer.innerHTML = '<div class="loading-comments"><div class="spinner"></div></div>';
                listContainer.hidden = false;
                commentsContainer.hidden = false;
            } else {
                 // Indicate loading in the button?
                 const btn = loadMoreContainer.querySelector('.load-more-comments-btn');
                 if (btn) btn.textContent = 'Loading...';
            }

            const response = await fetch(`/api/comments?subreddit=${encodeURIComponent(subreddit)}&post_id=${pid}&limit=${limit}`);
            const data = await response.json();
            
            if (data.comments && data.comments.length > 0) {
                listContainer.innerHTML = data.comments.map(c => createCommentHTML(c, collapsedIds)).join('');
                
                // Update load more button
                loadMoreContainer.innerHTML = `
                    <button class="btn btn-secondary btn-small load-more-comments-btn" style="width: 100%;">Load 3 more comments</button>
                `;
                loadMoreContainer.hidden = false;
                
                postElement.dataset.commentsLoaded = 'true';
                postElement.dataset.currentLimit = limit;
            } else {
                listContainer.innerHTML = '<div class="loading-comments">No comments yet.</div>';
            }
        } catch (err) {
            console.error('Error loading comments:', err);
            listContainer.innerHTML = '<div class="loading-comments" style="color: #ff5555;">Failed to load comments</div>';
        }
    }

    // Post click handler for expansion
    container.addEventListener('click', (e) => {
        const post = e.target.closest('.post');
        if (!post) return;
        
        // Ignore clicks on interactive elements and comments
        if (e.target.closest('a, button, video, audio, input, select, .video-controls, .gallery-nav, .search-form, .comment')) {
            return;
        }
        
        const textContent = post.querySelector('.post-text-content');
        const commentsContainer = post.querySelector('.post-top-comments');

        // Check if user clicked on the text content or the dedicated text toggle
        const clickedText = e.target.closest('.post-text-content, .post-text-toggle');

        // If clicked the text area/toggle, toggle text only and do not affect comments
        if (clickedText) {
            if (textContent) {
                textContent.classList.toggle('expanded');
            }
            return;
        }

        // Otherwise, clicking the post (outside the text toggle) follows existing behaviour:
        // toggle comments (and leave text state unchanged)
        let isExpandingComments = true;
        if (commentsContainer && !commentsContainer.hidden) isExpandingComments = false;

        if (commentsContainer) {
            if (isExpandingComments) {
                if (post.dataset.commentsLoaded !== 'true') {
                    loadTopComments(post);
                } else {
                    commentsContainer.hidden = false;
                }
            } else {
                commentsContainer.hidden = true;
            }
        }
    });

    // Intercept inline pin/unpin/ban form submissions and perform AJAX POSTs
    container.addEventListener('submit', async (e) => {
        const form = e.target;
        if (!form || !form.classList.contains('inline-form')) return;
        // Only handle pin/unpin/ban here
        const action = form.getAttribute('action') || '';
        if (!action.includes('/pin/') && !action.includes('/unpin/') && !action.includes('/ban/')) return;
        e.preventDefault();

        // visual feedback
        const submitBtn = form.querySelector('button[type="submit"]');
        const originalText = submitBtn ? submitBtn.textContent : null;
        if (submitBtn) { submitBtn.disabled = true; submitBtn.textContent = '…'; }

        try {
            const formData = new FormData(form);
            const resp = await fetch(action, {
                method: 'POST',
                headers: { 'X-CSRFToken': window.csrfToken },
                body: new URLSearchParams(formData)
            });

            if (!resp.ok) throw new Error('Request failed');

            // Update UI locally to avoid full reload
            if (action.includes('/pin/')) {
                const subreddit = action.split('/pin/').pop();
                if (!feedPinnedSubs.includes(subreddit)) feedPinnedSubs.push(subreddit);
                if (!pinnedSubs.includes(subreddit)) pinnedSubs.push(subreddit);
                // convert form into unpin form
                form.setAttribute('action', `/unpin/${subreddit}`);
                if (submitBtn) { submitBtn.textContent = '📍'; submitBtn.title = `Unpin r/${subreddit}`; submitBtn.classList.remove('pin-btn'); submitBtn.classList.add('unpin-btn'); }
                refreshPinnedNav();
            } else if (action.includes('/unpin/')) {
                const subreddit = action.split('/unpin/').pop();
                feedPinnedSubs = feedPinnedSubs.filter(s => s !== subreddit);
                pinnedSubs = pinnedSubs.filter(s => s !== subreddit);
                form.setAttribute('action', `/pin/${subreddit}`);
                if (submitBtn) { submitBtn.textContent = '📌'; submitBtn.title = `Pin r/${subreddit}`; submitBtn.classList.remove('unpin-btn'); submitBtn.classList.add('pin-btn'); }
                refreshPinnedNav();
            } else if (action.includes('/ban/')) {
                const subreddit = action.split('/ban/').pop();
                // remove posts from this subreddit from the DOM
                document.querySelectorAll(`.post[data-subreddit="${subreddit}"]`).forEach(p => p.remove());
            }
        } catch (err) {
            console.error('Inline action failed', err);
            // fallback: full reload so the server state is reflected
            window.location.reload();
        } finally {
            if (submitBtn) { submitBtn.disabled = false; }
        }
    });

    // Initialize video controls for newly added posts
    function initVideoControls(container) {
        // Trigger DOMContentLoaded-like initialization for new videos
        const event = new CustomEvent('newPostsAdded', { detail: { container } });
        document.dispatchEvent(event);
    }
    
    async function loadMorePosts() {
        if (loading || noMorePosts || !after) return;
        
        loading = true;
        loadingIndicator.style.display = 'block';
        
        try {
            const response = await fetch(`/api/posts?subreddit=${encodeURIComponent(subreddit)}&sort=${encodeURIComponent(sort)}&t=${encodeURIComponent(timeFilter)}&after=${encodeURIComponent(after)}`);
            const data = await response.json();
            
            if (data.posts && data.posts.length > 0) {
                data.posts.forEach(post => {
                    postCount++;
                    const postHTML = createPostHTML(post, postCount);
                    container.insertAdjacentHTML('beforeend', postHTML);
                    
                    // Add to mini-nav
                    addToMiniNav(post, postCount);
                });
                
                after = data.after;
                container.dataset.after = after || '';
                
                if (!after) {
                    noMorePosts = true;
                    noMoreIndicator.style.display = 'block';
                }
                
                // Re-initialize video controls for new posts
                initVideoControls(container);
                setupTriggerObserver();
            } else {
                noMorePosts = true;
                noMoreIndicator.style.display = 'block';
            }
        } catch (err) {
            console.error('Error loading more posts:', err);
        } finally {
            loading = false;
            loadingIndicator.style.display = 'none';
        }
    }
    
    // Observer for triggering load at post 20 (or 5 posts before end)
    function setupTriggerObserver() {
        const posts = document.querySelectorAll('.post');
        const triggerIndex = Math.max(posts.length - 5, 20);
        const triggerPost = posts[triggerIndex - 1];
        
        if (!triggerPost || triggerPost.dataset.observed) return;
        
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    loadMorePosts();
                    observer.disconnect();
                }
            });
        }, { threshold: 0.1 });
        
        triggerPost.dataset.observed = 'true';
        observer.observe(triggerPost);
    }
    
    // Add post to mini-nav
    function addToMiniNav(post, index) {
        const miniNavItems = document.getElementById('mini-nav-items');
        if (!miniNavItems) return;
        
        const thumbnail = post.thumbnail || post.image_url || '';
        const isValidThumb = thumbnail && thumbnail.startsWith('http');
        
        let content;
        if (isValidThumb) {
            const safeThumb = escapeHTML(thumbnail);
            content = `<img src="${safeThumb}" alt="" class="mini-nav-thumb">`;
        } else if (post.is_self) {
            content = `<div class="mini-nav-placeholder">📝</div>`;
        } else {
            content = `<div class="mini-nav-placeholder">🔗</div>`;
        }
        
        const item = document.createElement('a');
        item.href = `#post-${index}`;
        item.className = 'mini-nav-item';
        item.dataset.postIndex = index;
        item.title = post.title;
        item.innerHTML = content;
        miniNavItems.appendChild(item);
    }
    
    // Handle load more comments button click
    container.addEventListener('click', (e) => {
        if (e.target.matches('.load-more-comments-btn')) {
            e.stopPropagation(); // Prevent post expansion logic
            const post = e.target.closest('.post');
            if (post) {
                const currentLimit = parseInt(post.dataset.currentLimit || 3);
                const newLimit = currentLimit + 3;
                loadTopComments(post, newLimit);
            }
        }
    });
    
    // Initial setup
    if (after) {
        setupTriggerObserver();
    }
    
    // Mini-nav minimap functionality (like VS Code)
    const miniNav = document.getElementById('mini-nav');
    const miniNavItems = document.getElementById('mini-nav-items');
    const miniNavViewport = document.getElementById('mini-nav-viewport');
    
    if (miniNav && miniNavItems && miniNavViewport) {
        let isDraggingViewport = false;
        let dragStartY = 0;
        let dragStartScroll = 0;
        
        // Update viewport indicator position and size based on actual visible posts
        function updateViewportIndicator() {
            const maxPageScroll = document.documentElement.scrollHeight - window.innerHeight;
            const currentPageScroll = window.pageYOffset || document.documentElement.scrollTop;
            const scrollRatio = maxPageScroll > 0 ? currentPageScroll / maxPageScroll : 0;
            
            // Sync mini-nav items scroll
            const maxNavScroll = miniNavItems.scrollHeight - miniNavItems.clientHeight;
            miniNavItems.scrollTop = scrollRatio * maxNavScroll;
            
            // Find which posts are actually visible in the browser viewport
            const posts = document.querySelectorAll('.post');
            const vpTop = 0;
            const vpBottom = window.innerHeight;
            let firstVisibleIndex = null;
            let lastVisibleIndex = null;
            let firstVisibleRatio = 1;   // fraction of first visible post that's on screen
            let lastVisibleRatio = 1;    // fraction of last visible post that's on screen
            let closestPost = null;
            let closestDistance = Infinity;
            const viewportCenter = vpBottom / 2;

            posts.forEach(post => {
                const rect = post.getBoundingClientRect();
                // A post is visible if it overlaps the viewport at all
                if (rect.bottom > vpTop && rect.top < vpBottom) {
                    const idx = post.dataset.postIndex;
                    if (idx) {
                        // How much of this post is visible (0..1)
                        const visibleTop = Math.max(vpTop, rect.top);
                        const visibleBottom = Math.min(vpBottom, rect.bottom);
                        const postHeight = rect.height || 1;
                        const ratio = Math.max(0, (visibleBottom - visibleTop) / postHeight);

                        if (firstVisibleIndex === null) {
                            firstVisibleIndex = idx;
                            firstVisibleRatio = ratio;
                        }
                        lastVisibleIndex = idx;
                        lastVisibleRatio = ratio;
                    }
                }
                // Track closest-to-center for active highlighting
                const postCenter = rect.top + rect.height / 2;
                const distance = Math.abs(postCenter - viewportCenter);
                if (distance < closestDistance) {
                    closestDistance = distance;
                    closestPost = post;
                }
            });

            // Position the ghost box to span the nav items of visible posts
            const miniNavRect = miniNav.getBoundingClientRect();
            const itemsRect = miniNavItems.getBoundingClientRect();
            const itemsTopOffset = Math.max(0, itemsRect.top - miniNavRect.top);
            const itemsVisibleHeight = itemsRect.height;

            if (firstVisibleIndex !== null && lastVisibleIndex !== null) {
                const firstNav = miniNavItems.querySelector(`[data-post-index="${firstVisibleIndex}"]`);
                const lastNav = miniNavItems.querySelector(`[data-post-index="${lastVisibleIndex}"]`);
                if (firstNav && lastNav) {
                    // Get nav item positions relative to miniNav
                    const firstRect = firstNav.getBoundingClientRect();
                    const lastRect = lastNav.getBoundingClientRect();
                    const firstNavHeight = firstRect.height;
                    const lastNavHeight = lastRect.height;

                    // Offset into the first nav item by the hidden portion
                    // e.g. if 30% of the first post is visible, skip 70% of its nav item
                    const firstHiddenFraction = 1 - firstVisibleRatio;
                    const ghostTop = (firstRect.top - miniNavRect.top) + (firstNavHeight * firstHiddenFraction);

                    // Trim the last nav item by its hidden portion
                    const lastHiddenFraction = 1 - lastVisibleRatio;
                    const ghostBottom = (lastRect.bottom - miniNavRect.top) - (lastNavHeight * lastHiddenFraction);

                    const ghostHeight = Math.max(16, ghostBottom - ghostTop);
                    // Clamp within the visible items area
                    const clampedTop = Math.max(itemsTopOffset, Math.min(ghostTop, itemsTopOffset + itemsVisibleHeight - ghostHeight));
                    const clampedHeight = Math.min(ghostHeight, itemsTopOffset + itemsVisibleHeight - clampedTop);

                    miniNavViewport.style.top = clampedTop + 'px';
                    miniNavViewport.style.height = Math.max(20, clampedHeight) + 'px';
                }
            } else {
                // Fallback: proportional positioning (e.g. before first post or after last)
                const viewportRatio = window.innerHeight / (document.documentElement.scrollHeight || 1);
                const indicatorHeight = Math.max(30, itemsVisibleHeight * viewportRatio);
                const indicatorTop = itemsTopOffset + scrollRatio * (itemsVisibleHeight - indicatorHeight);
                miniNavViewport.style.height = indicatorHeight + 'px';
                miniNavViewport.style.top = Math.max(itemsTopOffset, indicatorTop) + 'px';
            }

            // Update active post highlighting
            if (closestPost) {
                const index = closestPost.dataset.postIndex;
                const navItem = miniNav.querySelector(`[data-post-index="${index}"]`);
                if (navItem) {
                    miniNav.querySelectorAll('.mini-nav-item').forEach(i => i.classList.remove('active'));
                    navItem.classList.add('active');
                }
            }
        }
        
        // Click on minimap to jump to position
        miniNav.addEventListener('mousedown', (e) => {
            if (e.target === miniNavViewport || miniNavViewport.contains(e.target)) {
                // Start dragging viewport
                isDraggingViewport = true;
                dragStartY = e.clientY;
                dragStartScroll = window.pageYOffset || document.documentElement.scrollTop;
                e.preventDefault();
            } else if (e.target === miniNav || e.target === miniNavItems || miniNavItems.contains(e.target)) {
                // Items have pointer-events:none so e.target is never a nav item.
                // Determine which nav item is at the click Y by checking bounding rects.
                const clickY = e.clientY;
                let hitItem = null;
                const items = miniNavItems.querySelectorAll('.mini-nav-item');
                for (const item of items) {
                    const r = item.getBoundingClientRect();
                    if (clickY >= r.top && clickY <= r.bottom) {
                        hitItem = item;
                        break;
                    }
                }
                if (hitItem) {
                    const postIndex = hitItem.dataset.postIndex;
                    const targetPost = document.getElementById('post-' + postIndex);
                    if (targetPost) {
                        targetPost.scrollIntoView({ behavior: 'smooth', block: 'center' });
                        e.preventDefault();
                        return;
                    }
                }
                // Click on empty space — jump to proportional position
                const rect = miniNavItems.getBoundingClientRect();
                const clickRatio = (e.clientY - rect.top) / rect.height;
                const maxPageScroll = document.documentElement.scrollHeight - window.innerHeight;
                const targetScroll = clickRatio * maxPageScroll;
                window.scrollTo(0, targetScroll);
                e.preventDefault();
            }
        });
        
        // Drag viewport to scroll
        document.addEventListener('mousemove', (e) => {
            if (isDraggingViewport) {
                const deltaY = e.clientY - dragStartY;
                const miniNavHeight = miniNavItems.clientHeight;
                const maxPageScroll = document.documentElement.scrollHeight - window.innerHeight;
                const scrollDelta = (deltaY / miniNavHeight) * maxPageScroll;
                window.scrollTo(0, dragStartScroll + scrollDelta);
                e.preventDefault();
            }
        });
        
        document.addEventListener('mouseup', () => {
            isDraggingViewport = false;
        });
        
        // Throttle with rAF so we run at most once per frame
        let vpTicking = false;
        function scheduleViewportUpdate() {
            if (!vpTicking) {
                vpTicking = true;
                requestAnimationFrame(() => {
                    updateViewportIndicator();
                    vpTicking = false;
                });
            }
        }
        window.addEventListener('scroll', scheduleViewportUpdate, { passive: true });
        window.addEventListener('resize', scheduleViewportUpdate, { passive: true });

        const postsContainer = document.getElementById('posts-container');
        if (window.ResizeObserver && postsContainer) {
            const resizeObserver = new ResizeObserver(() => {
                updateViewportIndicator();
            });
            resizeObserver.observe(postsContainer);
        }
        
        // Adjust sidebar position based on header visibility
        function updateNavPosition() {
            const header = document.querySelector('.header');
            if (header) {
                const isHidden = header.classList.contains('header-hidden');
                miniNav.style.setProperty('--nav-top', isHidden ? '20px' : '70px');
                // Update viewport indicator when header position changes
                setTimeout(updateViewportIndicator, 350);
            }
        }
        
        // Watch for header class changes
        const header = document.querySelector('.header');
        if (header) {
            const observer = new MutationObserver(updateNavPosition);
            observer.observe(header, { attributes: true, attributeFilter: ['class'] });
            updateNavPosition();
        }
        
        // Initial update
        updateViewportIndicator();
    }

    // Meta-action condensed menu for narrow screens
    document.addEventListener('click', (e) => {
        const toggle = e.target.closest('.meta-menu-toggle');
        if (toggle) {
            e.stopPropagation();
            const post = toggle.closest('.post');
            if (!post) return;
            const menu = post.querySelector('.meta-menu');
            const actions = post.querySelector('.post-meta-actions');
            if (!menu || !actions) return;
            if (menu.hidden) {
                // populate and show
                // Clone actions into the menu, then append readable labels from title attributes
                menu.innerHTML = actions.innerHTML;
                // Remove non-interactive upvotes from the dropdown menu (keep them visible in header)
                menu.querySelectorAll('.post-upvotes').forEach(n => n.remove());
                // For each action (button/link/form) append a text label using the title/aria-label
                menu.querySelectorAll('.meta-action-btn, form.inline-form').forEach(node => {
                    if (node.tagName === 'FORM') {
                        const btn = node.querySelector('button');
                        if (btn) {
                            // Prefer a short static label for pin/ban actions to avoid showing subreddit name
                            let labelText = '';
                            if (btn.classList.contains('pin-btn')) labelText = 'Pin';
                            else if (btn.classList.contains('unpin-btn')) labelText = 'Unpin';
                            else if (btn.classList.contains('ban-btn')) labelText = 'Ban';
                            else labelText = (btn.getAttribute('title') || btn.getAttribute('aria-label') || btn.textContent || '').replace(/\s*r\//, '').replace(/\(.+\)/, '').trim();

                            if (!btn.querySelector('.meta-action-label')) {
                                const span = document.createElement('span');
                                span.className = 'meta-action-label';
                                span.textContent = labelText ? (' ' + labelText) : '';
                                btn.appendChild(span);
                            }
                        }
                    } else {
                        // node is a link/button element
                        // for certain button classes prefer short labels
                        let labelText = '';
                        if (node.classList && node.classList.contains('pin-btn')) labelText = 'Pin';
                        else if (node.classList && node.classList.contains('unpin-btn')) labelText = 'Unpin';
                        else if (node.classList && node.classList.contains('ban-btn')) labelText = 'Ban';
                        else labelText = (node.getAttribute('title') || node.getAttribute('aria-label') || node.textContent || '').replace(/\s*r\//, '').replace(/\(.+\)/, '').trim();

                        if (!node.querySelector || !node.querySelector('.meta-action-label')) {
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
                // attach share handlers and other dynamic handlers
                setupShareButtons(menu);

                // Position menu under the toggle button (relative to the post)
                menu.style.right = 'auto';
                const toggleRect = toggle.getBoundingClientRect();
                const postRect = post.getBoundingClientRect();
                let left = toggleRect.left - postRect.left;
                let top = toggleRect.bottom - postRect.top;

                // apply initial position
                menu.style.left = left + 'px';
                menu.style.top = top + 'px';

                // adjust to avoid overflow to the right
                const menuRect = menu.getBoundingClientRect();
                const overflowRight = (menuRect.right - postRect.right);
                if (overflowRight > 0) {
                    left = left - overflowRight - 8;
                    menu.style.left = Math.max(8, left) + 'px';
                }

                // ensure menu doesn't go off the left edge
                const updatedMenuRect = menu.getBoundingClientRect();
                if (updatedMenuRect.left < postRect.left + 8) {
                    menu.style.left = '8px';
                }

            } else {
                menu.hidden = true;
                menu.setAttribute('aria-hidden', 'true');
                toggle.setAttribute('aria-expanded', 'false');
                menu.style.left = '';
                menu.style.top = '';
                menu.style.right = '';
            }
            return;
        }

        // Close any open meta menus when clicking outside
        document.querySelectorAll('.meta-menu').forEach(m => {
            if (!m.hidden) {
                m.hidden = true;
                m.setAttribute('aria-hidden', 'true');
                const t = m.closest('.post') ? m.closest('.post').querySelector('.meta-menu-toggle') : null;
                if (t) t.setAttribute('aria-expanded', 'false');
            }
        });
    }, true);

    // Hide menus on resize to avoid stale state
    window.addEventListener('resize', () => {
        if (window.innerWidth > 480) {
            document.querySelectorAll('.meta-menu').forEach(m => { m.hidden = true; m.setAttribute('aria-hidden','true'); });
            document.querySelectorAll('.meta-menu-toggle').forEach(t => t.setAttribute('aria-expanded','false'));
        }
    });
})();
