import { SYN } from "../../utils/theme";

export type Kind = keyof typeof SYN;
export interface Tok { t: string; k: Kind }

const ASM = new Set(["asm", "nasm", "x86", "x64", "x86_64", "assembly", "gas", "masm", "arm", "armv8"]);
const C_KW = "if|else|for|while|return|struct|union|enum|typedef|static|const|sizeof|switch|case|break|continue|goto|include|define|void|int|char|long|short|unsigned|signed|float|double|size_t|uint8_t|uint16_t|uint32_t|uint64_t";
const PY_KW = "def|return|import|from|if|elif|else|for|while|class|try|except|finally|with|as|in|not|and|or|is|None|True|False|lambda|yield|raise|async|await|print";
const JS_KW = "const|let|var|function|return|if|else|for|while|class|new|import|export|from|await|async|try|catch|throw|null|undefined|true|false|typeof";
const SQL_KW = "SELECT|FROM|WHERE|INSERT|INTO|VALUES|UPDATE|SET|DELETE|JOIN|ON|AND|OR|UNION|ORDER|BY|GROUP|LIMIT|DROP|TABLE|NULL|LIKE";
const SH_KW = "if|then|else|fi|for|do|done|while|case|esac|function|export|sudo|echo|cd|ls|cat|grep|curl|chmod|nmap|gdb|python3?|nc";
const REG = "(?:[re]?(?:ax|bx|cx|dx|si|di|sp|bp|ip)|r(?:8|9|1[0-5])[dwb]?|[abcd][lh]|[sd]il|[sb]pl|xmm\\d+|eflags|rflags|cs|ds|es|ss|fs|gs|pc|lr|x\\d{1,2}|w\\d{1,2})";

const rxFor = (lang: string) => {
  const l = (lang || "").toLowerCase();
  const comment = ASM.has(l) ? ";.*$|//.*$|#.*$" : ["python", "py", "bash", "sh", "shell", "zsh", "ruby"].includes(l) ? "#.*$" : l === "sql" ? "--.*$" : "//.*$|/\\*.*?\\*/";
  const kw = ASM.has(l) ? "$^" : ["python", "py"].includes(l) ? PY_KW : ["js", "javascript", "ts", "typescript"].includes(l) ? JS_KW : l === "sql" ? SQL_KW : ["bash", "sh", "shell", "zsh"].includes(l) ? SH_KW : C_KW;
  return new RegExp(`(${comment})|("(?:[^"\\\\]|\\\\.)*"|'(?:[^'\\\\]|\\\\.)*')|(\\b0x[0-9a-fA-F]+\\b|\\b\\d+\\b)|(%?\\b${REG}\\b)|(\\b(?:${kw})\\b)|([A-Za-z_][\\w.]*)(?=\\s*\\()`, l === "sql" ? "gi" : "g");
};

/** Small deterministic highlighter (no runtime dependency, no async grammar load). Good enough for teaching snippets. */
export const highlight = (line: string, lang: string): Tok[] => {
  const out: Tok[] = [];
  const asm = ASM.has((lang || "").toLowerCase());
  let rest = line, head = "";
  if (asm) { // label or mnemonic leads the line
    const m = /^(\s*)([A-Za-z_.][\w.]*:)(.*)$/.exec(line);
    if (m) { out.push({ t: m[1], k: "plain" }, { t: m[2], k: "fn" }); rest = m[3]; }
    else {
      const mm = /^(\s*)([a-z][a-z0-9]{1,7})(\b.*)$/i.exec(line);
      if (mm && !mm[2].startsWith("0x")) { out.push({ t: mm[1], k: "plain" }, { t: mm[2], k: "mnemonic" }); rest = mm[3]; }
    }
  }
  void head;
  const rx = rxFor(lang);
  let last = 0, m: RegExpExecArray | null;
  while ((m = rx.exec(rest))) {
    if (m.index > last) out.push({ t: rest.slice(last, m.index), k: "plain" });
    const k: Kind = m[1] ? "comment" : m[2] ? "string" : m[3] ? (asm && /^0x/i.test(m[3]) ? "addr" : "number") : m[4] ? "reg" : m[5] ? "keyword" : "fn";
    out.push({ t: m[0], k });
    last = m.index + m[0].length;
    if (m[0].length === 0) rx.lastIndex++;
  }
  if (last < rest.length) out.push({ t: rest.slice(last), k: "plain" });
  return out;
};

/** tokens clipped to the first `n` characters (for typing animations) */
export const clipTokens = (toks: Tok[], n: number): Tok[] => {
  const res: Tok[] = []; let left = n;
  for (const t of toks) {
    if (left <= 0) break;
    res.push(left >= t.t.length ? t : { ...t, t: t.t.slice(0, left) });
    left -= t.t.length;
  }
  return res;
};
