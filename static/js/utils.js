// Utility functions for Vigzone AI

/**
 * Escape HTML special characters to prevent XSS
 * @param {string} str - String to escape
 * @returns {string} - Escaped string
 */
function escapeHtml(str){
    return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

/**
 * Generate a unique ID
 * @returns {string} - Unique ID
 */
function genId(){
    return 'c' + Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
}

/**
 * Extract title from messages for conversation history
 * @param {Array} msgs - Array of message objects
 * @returns {string} - Title for conversation
 */
function titleFromMessages(msgs){
    const firstUser = (msgs || []).find(m => m.role === 'user');
    if (!firstUser) return 'New chat';
    let t = firstUser.displayText !== undefined ? firstUser.displayText : (typeof firstUser.content === 'string' ? firstUser.content : '');
    t = (t || '').replace(/\s+/g, ' ').trim();
    if (!t) return firstUser.imageSrc ? 'Generated image' : 'New chat';
    return t.length > 48 ? t.slice(0, 48) + '…' : t;
}

/**
 * Syntax highlighting for code blocks
 * @param {string} code - Code to highlight
 * @param {string} lang - Language identifier
 * @returns {string} - HTML with syntax highlighting
 */
function highlightCode(code, lang){
    const keywords = ['def','class','if','elif','else','for','while','return','import','from','as','try','except',
      'finally','with','raise','pass','break','continue','and','or','not','in','is','lambda','yield','global',
      'nonlocal','assert','del','async','await','const','let','var','function','new','this','extends','export',
      'default','catch','throw','typeof','instanceof','void','delete','of','static','public','private','protected',
      'interface','type','enum','implements','package','abstract','final','native','synchronized','transient',
      'volatile','throws','super','true','false','null','undefined','None','True','False','self',
      // Go
      'func','defer','go','chan','select','range','struct','fallthrough','goto',
      // Rust
      'fn','let','mut','impl','trait','match','pub','use','mod','crate','where','unsafe','dyn','move','ref','loop',
      // C / C++ / C#
      'include','define','typedef','namespace','template','sizeof','nullptr','NULL','char','double','long','short',
      'unsigned','signed','extern','inline','using','virtual','override','friend',
      // PHP
      'echo','require','require_once','include_once','foreach','elseif','endif','array','isset','empty',
      // Ruby
      'end','module','then','unless','until','elsif','require','nil','begin','rescue','ensure','raise',
      'attr_accessor','attr_reader','attr_writer'
    ];
    const builtins = ['print','len','range','str','int','float','list','dict','set','tuple','bool','isinstance',
      'getattr','setattr','hasattr','open','input','map','filter','zip','enumerate','sorted','reversed','min','max',
      'sum','abs','round','any','all','next','iter','format','super','property','classmethod','staticmethod',
      'console','document','window','Math','JSON','Array','Object','String','Number','Boolean','Date','RegExp',
      'Error','Promise','Map','Set','Symbol','Proxy','Reflect',
      'fmt','Println','Printf','Sprintf','append','cap','copy',
      'println','vec','Vec','Box','Option','Some','None','Ok','Err','Self',
      'printf','scanf','malloc','free','puts'
    ];
    let result = '';
    let i = 0;
    const src = code;
    while(i < src.length){
        // Decorators / annotations (e.g. @staticmethod, @Override, @app.route)
        if(src[i] === '@' && /[A-Za-z_]/.test(src[i+1] || '')){
            let end = i + 1;
            while(end < src.length && /[A-Za-z0-9_]/.test(src[end])) end++;
            result += '<span class="tok-deco">' + escapeHtml(src.slice(i, end)) + '</span>';
            i = end;
            continue;
        }
        // Comments
        if(src[i] === '#'){
            let end = src.indexOf('\n', i);
            if(end === -1) end = src.length;
            result += '<span class="tok-cmt">' + escapeHtml(src.slice(i, end)) + '</span>';
            i = end;
            continue;
        }
        if(src[i] === '/' && src[i+1] === '/'){
            let end = src.indexOf('\n', i);
            if(end === -1) end = src.length;
            result += '<span class="tok-cmt">' + escapeHtml(src.slice(i, end)) + '</span>';
            i = end;
            continue;
        }
        if(src[i] === '/' && src[i+1] === '*'){
            let end = src.indexOf('*/', i+2);
            if(end === -1) end = src.length; else end += 2;
            result += '<span class="tok-cmt">' + escapeHtml(src.slice(i, end)) + '</span>';
            i = end;
            continue;
        }
        // Strings (single, double, triple, template literals)
        if(src[i] === '"' || src[i] === "'" || src[i] === '`'){
            const q = src[i];
            let end = i + 1;
            // triple quotes
            if(src.slice(i, i+3) === q+q+q){
                end = src.indexOf(q+q+q, i+3);
                if(end === -1) end = src.length; else end += 3;
            } else {
                while(end < src.length && src[end] !== q && src[end] !== '\n'){
                    if(src[end] === '\\') end++;
                    end++;
                }
                if(end < src.length && src[end] === q) end++;
            }
            const raw = src.slice(i, end);
            const escRaw = escapeHtml(raw);
            let inner;
            if(q !== '`' && /^f["']/.test(raw)){
                // Python f-string: highlight {expr} segments
                inner = escRaw.replace(/\{([^}]+)\}/g, '</span><span class="tok-op">{</span>$1<span class="tok-op">}</span><span class="tok-str">');
            } else if(q === '`'){
                // JS template literal: highlight ${expr} segments
                inner = escRaw.replace(/\$\{([^}]+)\}/g, '</span><span class="tok-op">${</span>$1<span class="tok-op">}</span><span class="tok-str">');
            } else {
                inner = escRaw;
            }
            result += '<span class="tok-str">' + inner + '</span>';
            i = end;
            continue;
        }
        // Numbers
        if(/[0-9]/.test(src[i]) && (i === 0 || /[\s,;:=+\-*/%(<>[\]{}!&|^~]/.test(src[i-1]))){
            let end = i;
            while(end < src.length && /[0-9.xXa-fA-FeE_]/.test(src[end])) end++;
            result += '<span class="tok-num">' + src.slice(i, end) + '</span>';
            i = end;
            continue;
        }
        // Identifiers (keywords, builtins, functions)
        if(/[a-zA-Z_]/.test(src[i])){
            let end = i;
            while(end < src.length && /[a-zA-Z0-9_]/.test(src[end])) end++;
            const word = src.slice(i, end);
            if(keywords.includes(word)){
                result += '<span class="tok-kw">' + word + '</span>';
            } else if(builtins.includes(word)){
                result += '<span class="tok-bi">' + word + '</span>';
            } else if(end < src.length && src[end] === '('){
                result += '<span class="tok-fn">' + word + '</span>';
            } else {
                result += word;
            }
            i = end;
            continue;
        }
        // Operators
        if('+-*/%=<>!&|^~?:'.includes(src[i])){
            result += '<span class="tok-op">' + escapeHtml(src[i]) + '</span>';
            i++;
            continue;
        }
        result += escapeHtml(src[i]);
        i++;
    }

    // Highlight the type/class/function name that follows a declaration keyword,
    // regardless of which language fence was used (works across Python/JS/Go/Rust/Java/C#/etc.)
    result = result.replace(/(<span class="tok-kw">(?:class|struct|interface|trait|enum)<\/span>\s+)(\w+)/g, '$1<span class="tok-fn">$2</span>');
    result = result.replace(/(<span class="tok-kw">(?:def|function|fn|func)<\/span>\s+)(\w+)/g, '$1<span class="tok-fn">$2</span>');

    return result;
}