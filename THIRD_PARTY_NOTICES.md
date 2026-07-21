# Third-party notices

Content Masking Tool is licensed under GNU AGPL-3.0-only. It depends on
third-party packages that retain their own copyright and license terms.

The principal runtime dependencies are:

| Component | License reported by installed package metadata | Project |
|---|---|---|
| Microsoft Presidio Analyzer / Anonymizer | MIT | https://github.com/data-privacy-stack/presidio |
| markdown-it-py | MIT | https://github.com/executablebooks/markdown-it-py |
| python-docx | MIT | https://github.com/python-openxml/python-docx |
| PyMuPDF / MuPDF | GNU AGPL-3.0 or Artifex commercial license | https://github.com/pymupdf/PyMuPDF |
| platformdirs | MIT | https://github.com/tox-dev/platformdirs |
| Model Context Protocol Python SDK | MIT | https://github.com/modelcontextprotocol/python-sdk |
| tkinterdnd2 | MIT | https://github.com/Eliav2/tkinterdnd2 |
| spaCy | MIT | https://github.com/explosion/spaCy |
| en_core_web_sm | MIT | https://github.com/explosion/spacy-models |

The complete locked Python and Node dependency inventories are recorded in
`uv.lock` and `packaging/mcpb/package-lock.json`. Frozen distributions include
third-party package data and notices collected by the packaging tools. Before
publishing a release, maintainers should regenerate and review the dependency
inventory because transitive dependencies can change when lockfiles change.

This notice is informational and does not replace the license text shipped by
each third-party component.
