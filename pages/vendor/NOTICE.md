# Browser dependencies

All executable runtime, package and PDF assets are served from this repository, not fetched from third-party services after sign-in. `manifest.json` records pinned versions, source URLs, byte sizes and SHA-256 hashes. CI verifies every recorded asset and audits the report packages and npm lockfile. Pyodide's registry lists other available packages, but they are not shipped or downloaded unless explicitly vendored; only micropip, openpyxl and et_xmlfile are used here. Image decoding is not a browser feature.

- Pyodide 314.0.8: https://github.com/pyodide/pyodide — Mozilla Public License 2.0; `LICENSE-PYODIDE.txt`.
- CPython 3.14.2 bundled in Pyodide: https://www.python.org/ — PSF license; `LICENSE-PYTHON.txt`.
- micropip 0.11.1: https://github.com/pyodide/micropip — MPL-2.0; wheel includes its license metadata.
- openpyxl 3.1.5: https://openpyxl.readthedocs.io/ — MIT; wheel includes license.
- et_xmlfile 2.0.0: https://foss.heptapod.net/openpyxl/et_xmlfile — MIT; wheel includes license.
- jsPDF 4.2.1: https://github.com/parallax/jsPDF — MIT; `LICENSE-jspdf.txt`.
- jsPDF-AutoTable 5.0.9: https://github.com/simonbengtsson/jsPDF-AutoTable — MIT; `LICENSE-jspdf-autotable.txt`.

The Python source bundle contains this repository's shared analytics/report model. It is regenerated deterministically by `scripts/build_pages.py`, not downloaded from a third party. Python image packages and ReportLab are not required/shipped for browser reports; the optional private backend continues to use its separately pinned requirements.
