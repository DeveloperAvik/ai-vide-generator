"""Spoken forms for technical terms. Applied to the text sent to the TTS engine ONLY; captions and stored narration keep the
original spelling. Acronyms that engines read as words get letter-by-letter forms; terms engines mispronounce get respellings."""
import re

SPOKEN = {
    "XSS": "X S S", "SQL": "S Q L", "SQLi": "S Q L injection", "CSRF": "C S R F", "SSRF": "S S R F", "IDOR": "eye-door",
    "ELF": "E L F", "ASLR": "A S L R", "NX": "N X", "DEP": "D E P", "PIE": "P I E", "ROP": "R O P", "EIP": "E I P", "RIP": "R I P",
    "GDB": "G D B", "HTTP": "H T T P", "HTTPS": "H T T P S", "TLS": "T L S", "SSL": "S S L", "DNS": "D N S", "TCP": "T C P",
    "UDP": "U D P", "API": "A P I", "URL": "U R L", "URI": "U R I", "HTML": "H T M L", "CSS": "C S S", "JSON": "Jason",
    "JWT": "J W T", "OWASP": "oh-wasp", "CWE": "C W E", "CVE": "C V E", "CVSS": "C V S S", "NIST": "nist", "CISA": "sisa",
    "CSP": "C S P", "CORS": "cors", "ORM": "O R M", "OAuth": "oh-auth", "SSH": "S S H", "IP": "I P", "OS": "O S", "UI": "U I",
    "PHP": "P H P", "JS": "JavaScript", "XML": "X M L", "XXE": "X X E", "RCE": "R C E", "LFI": "L F I", "SUID": "sue-id",
    "sudo": "sue-doo", "nginx": "engine-X", "MITRE": "my-ter", "ATT&CK": "attack",
}
_PATTERN = re.compile(r"(?<![\w])(" + "|".join(re.escape(k) for k in sorted(SPOKEN, key=len, reverse=True)) + r")(?![\w])")


def for_speech(text: str) -> str:
    return _PATTERN.sub(lambda m: SPOKEN[m.group(1)], text)
