"""
LaTeX Resume Parser — extracts clean text from .tex resume files
for use in AI analysis and tailoring prompts.
"""
import re
from pathlib import Path


# Common LaTeX commands to strip
_TEX_COMMANDS = re.compile(r'\\[a-zA-Z]+\*?(\[.*?\])?(\{[^}]*\})*', re.DOTALL)
_BRACES = re.compile(r'[{}]')
_COMMENTS = re.compile(r'%.*$', re.MULTILINE)
_MULTIPLE_NL = re.compile(r'\n{3,}')
_SECTION_HEADERS = re.compile(r'\\(?:section|subsection|subsubsection)\*?\{([^}]+)\}')
_ITEM = re.compile(r'\\item\s*')


def parse_tex_file(file_path: str) -> str:
    """Parse a .tex resume file and return clean plaintext."""
    path = Path(file_path)
    if not path.exists():
        return ""
    
    raw = path.read_text(encoding="utf-8", errors="ignore")
    return tex_to_text(raw)


def tex_to_text(tex_content: str) -> str:
    """Convert LaTeX string to plaintext."""
    text = tex_content

    # Remove comments
    text = _COMMENTS.sub('', text)

    # Remove LaTeX document structure commands
    text = re.sub(r'\\begin\{[^}]*\}', '\n', text)
    text = re.sub(r'\\end\{[^}]*\}', '\n', text)

    # Replace section headers with readable titles
    def replace_section(m):
        return f"\n\n== {m.group(1).upper()} ==\n"
    text = _SECTION_HEADERS.sub(replace_section, text)

    # Replace \item with bullet
    text = _ITEM.sub('• ', text)

    # Replace common formatting
    text = re.sub(r'\\textbf\{([^}]+)\}', r'\1', text)
    text = re.sub(r'\\textit\{([^}]+)\}', r'\1', text)
    text = re.sub(r'\\emph\{([^}]+)\}', r'\1', text)
    text = re.sub(r'\\href\{[^}]+\}\{([^}]+)\}', r'\1', text)
    text = re.sub(r'\\url\{([^}]+)\}', r'\1', text)
    text = re.sub(r'\\newline', '\n', text)
    text = re.sub(r'\\\\', '\n', text)
    text = re.sub(r'\\hline', '', text)
    text = re.sub(r'~', ' ', text)

    # Strip remaining LaTeX commands
    text = _TEX_COMMANDS.sub(' ', text)

    # Strip leftover braces
    text = _BRACES.sub('', text)

    # Clean whitespace
    text = re.sub(r'[ \t]+', ' ', text)
    text = _MULTIPLE_NL.sub('\n\n', text)

    return text.strip()


def extract_contact_info(tex_content: str) -> dict:
    """Try to extract name, email, phone from a .tex resume."""
    info = {
        "name": "",
        "email": "",
        "phone": "",
        "github": "",
        "linkedin": "",
    }
    
    # Email
    email_match = re.search(r'[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}', tex_content)
    if email_match:
        info["email"] = email_match.group(0)
    
    # Phone (Indian format or generic)
    phone_match = re.search(r'(?:\+91[-\s]?)?[6-9]\d{9}|(?:\+\d{1,3}[-\s]?)?\(?\d{3}\)?[-\s]?\d{3}[-\s]?\d{4}', tex_content)
    if phone_match:
        info["phone"] = phone_match.group(0)
    
    # GitHub
    gh_match = re.search(r'github\.com/([^\s{}\\,]+)', tex_content, re.IGNORECASE)
    if gh_match:
        info["github"] = f"https://github.com/{gh_match.group(1)}"
    
    # LinkedIn
    li_match = re.search(r'linkedin\.com/in/([^\s{}\\,]+)', tex_content, re.IGNORECASE)
    if li_match:
        info["linkedin"] = f"https://linkedin.com/in/{li_match.group(1)}"
    
    return info
