// Simple subreddit autocomplete for header search
(function () {
    const form = document.getElementById('header-search-form');
    if (!form) return;
    const input = form.querySelector('input[name="q"]');
    if (!input) return;

    let controller = null;
    let activeIndex = -1;

    const list = document.createElement('ul');
    list.className = 'autocomplete-list';
    list.style.display = 'none';
    list.setAttribute('role', 'listbox');
    form.appendChild(list);

    function clearList() {
        list.innerHTML = '';
        list.style.display = 'none';
        activeIndex = -1;
    }

    function render(items) {
        list.innerHTML = '';
        if (!items || items.length === 0) {
            clearList();
            return;
        }

        items.forEach((it, idx) => {
            const li = document.createElement('li');
            li.className = 'autocomplete-item';
            li.setAttribute('role', 'option');
            li.dataset.name = it.name;

            const name = document.createElement('div');
            name.className = 'autocomplete-name';
            name.textContent = it.name;

            const meta = document.createElement('div');
            meta.className = 'autocomplete-meta';
            const title = it.title || '';
            const subs = it.subscribers ? ` · ${it.subscribers.toLocaleString()} subscribers` : '';
            meta.textContent = title + subs;

            li.appendChild(name);
            li.appendChild(meta);

            li.addEventListener('mousedown', (e) => {
                // mousedown instead of click to avoid input blur before handler
                e.preventDefault();
                chooseItem(idx);
            });

            list.appendChild(li);
        });

        list.style.display = 'block';
        activeIndex = -1;
    }

    function chooseItem(idx) {
        const item = list.children[idx];
        if (!item) return;
        const name = item.dataset.name;
        if (!name) return;
        // Navigate directly to subreddit page
        window.location.href = `/r/${encodeURIComponent(name)}`;
    }

    function setActive(idx) {
        const children = Array.from(list.children);
        children.forEach((c, i) => c.classList.toggle('active', i === idx));
        activeIndex = idx;
    }

    function onKey(e) {
        if (list.style.display === 'none') return;
        if (e.key === 'ArrowDown') {
            e.preventDefault();
            const next = Math.min(activeIndex + 1, list.children.length - 1);
            setActive(next);
            ensureVisible(next);
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            const prev = Math.max(activeIndex - 1, 0);
            setActive(prev);
            ensureVisible(prev);
        } else if (e.key === 'Enter') {
            if (activeIndex >= 0) {
                e.preventDefault();
                chooseItem(activeIndex);
            }
        } else if (e.key === 'Escape') {
            clearList();
        }
    }

    function ensureVisible(idx) {
        const el = list.children[idx];
        if (!el) return;
        const rect = el.getBoundingClientRect();
        const parentRect = list.getBoundingClientRect();
        if (rect.bottom > parentRect.bottom) el.scrollIntoView(false);
        if (rect.top < parentRect.top) el.scrollIntoView();
    }

    function debounce(func, wait) {
        let timeout = null;
        return function () {
            const args = arguments;
            clearTimeout(timeout);
            timeout = setTimeout(() => func.apply(null, args), wait);
        };
    }

    async function fetchSuggestions(q) {
        if (controller) controller.abort();
        controller = new AbortController();
        try {
            const resp = await fetch(`/api/subreddit_autocomplete?q=${encodeURIComponent(q)}&limit=8`, {
                signal: controller.signal,
                credentials: 'same-origin'
            });
            if (!resp.ok) return [];
            const j = await resp.json();
            return j.results || [];
        } catch (err) {
            if (err.name === 'AbortError') return [];
            return [];
        }
    }

    const debounced = debounce(async function () {
        const q = input.value.trim();
        if (!q) {
            clearList();
            return;
        }
        const items = await fetchSuggestions(q);
        render(items);
    }, 250);

    input.addEventListener('input', debounced);
    input.addEventListener('keydown', onKey);

    // Hide when clicking outside
    document.addEventListener('click', (e) => {
        if (!form.contains(e.target)) clearList();
    });

})();
