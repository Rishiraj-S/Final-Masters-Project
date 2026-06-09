window.dash_clientside = window.dash_clientside || {};

window.dash_clientside.seq_player = {
    /*
     * Generic shot-sequence player.
     * Works for both cc- and occ- prefixed modals — no component IDs referenced.
     *
     * Inputs:  n_intvl, r_nc, play_nc, prev_nc, next_nc
     * States:  frames (list of base64 PNGs), state {idx, playing, n_events, _r, _play, _prev, _next}
     * Outputs: [img src, new state, interval disabled, play-btn label, counter text]
     */
    play: function (n_intvl, r_nc, play_nc, prev_nc, next_nc, frames, state) {
        var nu = window.dash_clientside.no_update;
        if (!frames || !frames.length || !state) return [nu, nu, nu, nu, nu];

        var idx      = state.idx      !== undefined ? state.idx      : 0;
        var playing  = state.playing  !== undefined ? state.playing  : false;
        var n_events = state.n_events || frames.length;
        var n        = frames.length;
        var ni       = n_events > 0 ? Math.max(1, Math.floor(n / n_events)) : 1;

        // Baseline n_clicks stored in state (set when sequence loads)
        var pr = state._r    !== undefined ? state._r    : 0;
        var pp = state._play !== undefined ? state._play : 0;
        var pb = state._prev !== undefined ? state._prev : 0;
        var pn = state._next !== undefined ? state._next : 0;

        r_nc    = r_nc    || 0;
        play_nc = play_nc || 0;
        prev_nc = prev_nc || 0;
        next_nc = next_nc || 0;

        if      (r_nc > pr)    { idx = 0; playing = false; }
        else if (play_nc > pp) { playing = !playing; }
        else if (prev_nc > pb) { playing = false; idx = Math.max(0,   (Math.floor(idx / ni) - 1) * ni); }
        else if (next_nc > pn) { playing = false; idx = Math.min(n - 1, (Math.floor(idx / ni) + 1) * ni); }
        else if (playing)      { if (idx < n - 1) { idx++; } else { playing = false; } }

        var src  = "data:image/png;base64," + frames[idx];
        var eNum = Math.min(Math.floor(idx / ni) + 1, n_events);
        var ctr  = eNum + " / " + n_events;
        var ns   = {
            idx: idx, playing: playing, n_events: n_events,
            _r: r_nc, _play: play_nc, _prev: prev_nc, _next: next_nc
        };
        return [src, ns, !playing, playing ? "⏸" : "▶", ctr];
    }
};
