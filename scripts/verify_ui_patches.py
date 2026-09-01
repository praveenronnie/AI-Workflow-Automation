"""Verify all UI/background/content patches are present.

Run: python scripts/verify_ui_patches.py
"""
import glob


def _read(path):
    try:
        with open(path, encoding='utf-8') as fh:
            return fh.read()
    except FileNotFoundError:
        return ''


# The UI bundle is emitted by Vite with a content-hash filename (e.g.
# index-DVtXOa1C.js), so discover it dynamically instead of hard-coding a hash
# that goes stale on every rebuild. Missing optional artifacts (e.g.
# token-bridge.js) degrade to an empty string instead of aborting the run.
_bundles = sorted(glob.glob('openquire-ai-extension/ui/dist/assets/index-*.js'))
_t_path = _bundles[0] if _bundles else 'openquire-ai-extension/ui/dist/assets/index-DVtXOa1C.js'
t = _read(_t_path)
h = _read('openquire-ai-extension/ui/dist/index.html')
b = _read('openquire-ai-extension/background/background.js')
tb = _read('openquire-ai-extension/ui/dist/token-bridge.js')
c = _read('openquire-ai-extension/content/content.js')

BT = '`'
checks = {
    # --- auth/state patches (bundle) ---
    'P1 persist-auth': 'isAuthenticated:e.isAuthenticated,userEmail:e.userEmail' in t,
    'P1 no-panelOpen-persist': 'activityLog:e.activityLog,panelOpen:e.panelOpen' not in t,
    'P2 select-auth': ',isAuthenticated:s}=j();return(0,_.useEffect' in t,
    'P3 gate': 'e?(s?(0,L.jsxs)(' + BT + 'div' + BT in t and ']})):null)' in t,
    'P4 login-view': 'Sign in to continue' in t
                      and ']})):null)' in t,
    'P5 token-hydrate': 'window.__oqToken||localStorage.getItem' in t,
    'P6 logout-clear': 'chrome.storage.local.remove([' + BT + 'accessToken' + BT + '])' in t
                      and 'onClick:()=>{r(!1);try{localStorage.removeItem' in t,

    # --- CSP fix: bootstrap must be EXTERNAL ---
    'CSP no-inline-script': '<script>' not in h,
    'CSP external-bridge-ref': 'src="./token-bridge.js"' in h,
    'CSP bridge-file': '__oqToken' in tb and 'storage.onChanged' in tb,

    # --- React crash fix: zn hoisted before Rn ---
    'FIX-A zn-before-Rn': t.index('var zn=class{domain;')
                          < t.index('var Rn=class extends zn{'),
    'FIX-A old-trailing-def-gone': ',zn=class{domain;' not in t,

    # --- background auth guards ---
    'bg-401': 'AUTH_REQUIRED:' in b,
    'bg-guard': 'authRequired: true' in b,
    'bg-getToken': 'async getToken()' in b,
    'bg-onclick-gate': 'Only prefetch user data when a session exists' in b,
    'bg-logout': 'async logout()' in b,
    'bg-auth-state': 'isAuthenticated: extensionState.isAuthenticated' in b,
    'bg-catch-sendMessage': '.catch(() => {' in b,
    'bg-extensionState-auth': 'isAuthenticated: false' in b or 'isAuthenticated:false' in b,
    'bundle-auth-init': 'getToken' in t and 'setAuthenticated(!0)' in t,
    'bundle-update-ui-listener': 'UPDATE_UI_STATE' in t and 'chrome.runtime.onMessage.addListener' in t,
    'bundle-logout-bg': 'action:`logout`' in t,

    # --- content script classic-safe ---
    'FIX-C no-esm-import': 'import { buildSchema }' not in c,
    'FIX-C global-resolve': 'window.openquireExtractor' in c,
}
fails = 0
for k, v in checks.items():
    print(('PASS' if v else 'FAIL'), k)
    fails += 0 if v else 1
print('---')
print('ALL PASS' if fails == 0 else f'{fails} CHECK(S) FAILED')
