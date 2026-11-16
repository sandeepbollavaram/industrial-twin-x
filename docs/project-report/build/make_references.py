"""Build references.json and references.bib from verified Crossref records plus web sources.

Usage: python make_references.py <crossref.json>
The Crossref records were fetched from api.crossref.org during reference verification.
"""

import html
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ACCESSED = "Nov. 16, 2026"

# key -> DOI, for scholarly sources verified through Crossref.
DOI_KEYS = {
    "sisinni2018": "10.1109/TII.2018.2852491",
    "xu2014": "10.1109/TII.2014.2300753",
    "alfuqaha2015": "10.1109/COMST.2015.2444095",
    "lee2015": "10.1016/j.mfglet.2014.12.001",
    "leitao2016": "10.1016/j.compind.2015.08.004",
    "tao2019": "10.1109/TII.2018.2873186",
    "kritzinger2018": "10.1016/j.ifacol.2018.08.474",
    "fuller2020": "10.1109/ACCESS.2020.2998358",
    "jones2020": "10.1016/j.cirpj.2020.02.002",
    "rasheed2020": "10.1109/ACCESS.2020.2970143",
    "rosen2015": "10.1016/j.ifacol.2015.06.141",
    "grieves2017": "10.1007/978-3-319-38756-7_4",
    "jardine2006": "10.1016/j.ymssp.2005.09.012",
    "lei2018": "10.1016/j.ymssp.2017.11.016",
    "carvalho2019": "10.1016/j.cie.2019.106024",
    "zonta2020": "10.1016/j.cie.2020.106889",
    "chandola2009": "10.1145/1541880.1541882",
    "liu2008": "10.1109/ICDM.2008.17",
    "breiman2001": "10.1023/A:1010933404324",
    "harris2020": "10.1038/s41586-020-2649-2",
    "hunter2007": "10.1109/MCSE.2007.55",
    "niculescu2005": "10.1145/1102351.1102430",
    "kaufman2012": "10.1145/2382577.2382579",
    "roberts2017": "10.1111/ecog.02881",
    "saxena2008": "10.1109/PHM.2008.4711414",
    "boglietti2009": "10.1109/TIE.2008.2011622",
    "isermann2005": "10.1016/j.arcontrol.2004.12.002",
    "venkat2003": "10.1016/S0098-1354(02)00160-6",
    "ge2017": "10.1109/ACCESS.2017.2756872",
    "shi2016": "10.1109/JIOT.2016.2579198",
    "satya2017": "10.1109/MC.2017.9",
    "humayed2017": "10.1109/JIOT.2017.2703172",
    "cardenas2011": "10.1145/1966913.1966959",
    "liu2009": "10.1145/1653662.1653666",
    "langner2011": "10.1109/MSP.2011.67",
    "hunkeler2008": "10.1109/COMSWA.2008.4554519",
    "light2017": "10.21105/joss.00265",
    "nist80082": "10.6028/NIST.SP.800-82r3",
}

# Corrections where Crossref titles are truncated or need the full published form.
TITLE_FIX = {
    "chandola2009": "Anomaly detection: A survey",
    "cardenas2011": (
        "Attacks against process control systems: Risk assessment, detection, and response"
    ),
    "venkat2003": (
        "A review of process fault detection and diagnosis: Part I: Quantitative "
        "model-based methods"
    ),
    "hunkeler2008": "MQTT-S—A publish/subscribe protocol for wireless sensor networks",
    "humayed2017": "Cyber-physical systems security—A survey",
}
CONTAINER_FIX = {
    "liu2008": "Proc. 8th IEEE Int. Conf. Data Mining (ICDM)",
    "cardenas2011": "Proc. 6th ACM Symp. Information, Computer and Communications Security (ASIACCS)",
    "liu2009": "Proc. 16th ACM Conf. Computer and Communications Security (CCS)",
    "saxena2008": "Proc. Int. Conf. Prognostics and Health Management (PHM)",
    "niculescu2005": "Proc. 22nd Int. Conf. Machine Learning (ICML)",
    "hunkeler2008": "Proc. 3rd Int. Conf. Communication Systems Software and Middleware (COMSWARE)",
    "grieves2017": "Transdisciplinary Perspectives on Complex Systems, F.-J. Kahlen, S. Flumerfelt, and A. Alves, Eds. Cham, Switzerland: Springer",
}

WEB = {
    "mqtt311": {
        "ieee": "A. Banks and R. Gupta, Eds., “MQTT version 3.1.1,” OASIS Standard, Oct. 29, 2014. [Online]. Available: https://docs.oasis-open.org/mqtt/mqtt/v3.1.1/os/mqtt-v3.1.1-os.html (accessed {acc}).",
        "bib": "@techreport{{mqtt311, title={{MQTT Version 3.1.1}}, editor={{Banks, Andrew and Gupta, Rahul}}, institution={{OASIS}}, type={{OASIS Standard}}, year={{2014}}, url={{https://docs.oasis-open.org/mqtt/mqtt/v3.1.1/os/mqtt-v3.1.1-os.html}}}}",
    },
    "mqtt5": {
        "ieee": "A. Banks, E. Briggs, K. Borgendale, and R. Gupta, Eds., “MQTT version 5.0,” OASIS Standard, Mar. 7, 2019. [Online]. Available: https://docs.oasis-open.org/mqtt/mqtt/v5.0/mqtt-v5.0.html (accessed {acc}).",
        "bib": "@techreport{{mqtt5, title={{MQTT Version 5.0}}, editor={{Banks, Andrew and Briggs, Ed and Borgendale, Ken and Gupta, Rahul}}, institution={{OASIS}}, type={{OASIS Standard}}, year={{2019}}, url={{https://docs.oasis-open.org/mqtt/mqtt/v5.0/mqtt-v5.0.html}}}}",
    },
    "pedregosa2011": {
        "ieee": "F. Pedregosa et al., “Scikit-learn: Machine learning in Python,” J. Mach. Learn. Res., vol. 12, no. 85, pp. 2825–2830, 2011. [Online]. Available: https://jmlr.org/papers/v12/pedregosa11a.html",
        "bib": "@article{{pedregosa2011, title={{Scikit-learn: Machine Learning in Python}}, author={{Pedregosa, Fabian and others}}, journal={{Journal of Machine Learning Research}}, volume={{12}}, number={{85}}, pages={{2825--2830}}, year={{2011}}, url={{https://jmlr.org/papers/v12/pedregosa11a.html}}}}",
    },
    "isa62443": {
        "ieee": "International Society of Automation, “ISA/IEC 62443 series of standards.” [Online]. Available: https://www.isa.org/standards-and-publications/isa-standards/isa-iec-62443-series-of-standards (accessed {acc}).",
        "bib": "@misc{{isa62443, title={{ISA/IEC 62443 Series of Standards}}, author={{{{International Society of Automation}}}}, url={{https://www.isa.org/standards-and-publications/isa-standards/isa-iec-62443-series-of-standards}}, note={{Accessed 2026-11-16}}}}",
    },
    "opcua": {
        "ieee": "OPC Foundation, “Unified Architecture.” [Online]. Available: https://opcfoundation.org/about/opc-technologies/opc-ua/ (accessed {acc}).",
        "bib": "@misc{{opcua, title={{Unified Architecture}}, author={{{{OPC Foundation}}}}, url={{https://opcfoundation.org/about/opc-technologies/opc-ua/}}, note={{Accessed 2026-11-16}}}}",
    },
    "ditto": {
        "ieee": "Eclipse Foundation, “Eclipse Ditto: Overview.” [Online]. Available: https://eclipse.dev/ditto/intro-overview.html (accessed {acc}).",
        "bib": "@misc{{ditto, title={{Eclipse Ditto: Overview}}, author={{{{Eclipse Foundation}}}}, url={{https://eclipse.dev/ditto/intro-overview.html}}, note={{Accessed 2026-11-16}}}}",
    },
    "awsshadow": {
        "ieee": "Amazon Web Services, “Device Shadow service documents,” AWS IoT Core Developer Guide. [Online]. Available: https://docs.aws.amazon.com/iot/latest/developerguide/device-shadow-document.html (accessed {acc}).",
        "bib": "@misc{{awsshadow, title={{Device Shadow service documents}}, author={{{{Amazon Web Services}}}}, url={{https://docs.aws.amazon.com/iot/latest/developerguide/device-shadow-document.html}}, note={{Accessed 2026-11-16}}}}",
    },
    "simpy": {
        "ieee": "SimPy Developers, “SimPy: Discrete event simulation for Python,” documentation. [Online]. Available: https://simpy.readthedocs.io/en/latest/ (accessed {acc}).",
        "bib": "@misc{{simpy, title={{SimPy: Discrete event simulation for Python}}, author={{{{SimPy Developers}}}}, url={{https://simpy.readthedocs.io/en/latest/}}, note={{Accessed 2026-11-16}}}}",
    },
    "paho": {
        "ieee": "Eclipse Foundation, “Eclipse Paho MQTT Python client: Client module,” documentation. [Online]. Available: https://eclipse.dev/paho/files/paho.mqtt.python/html/client.html (accessed {acc}).",
        "bib": "@misc{{paho, title={{Eclipse Paho MQTT Python Client: client module}}, author={{{{Eclipse Foundation}}}}, url={{https://eclipse.dev/paho/files/paho.mqtt.python/html/client.html}}, note={{Accessed 2026-11-16}}}}",
    },
    "sklearn_iforest": {
        "ieee": "scikit-learn developers, “sklearn.ensemble.IsolationForest,” scikit-learn documentation. [Online]. Available: https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.IsolationForest.html (accessed {acc}).",
        "bib": "@misc{{sklearn_iforest, title={{sklearn.ensemble.IsolationForest}}, author={{{{scikit-learn developers}}}}, url={{https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.IsolationForest.html}}, note={{Accessed 2026-11-16}}}}",
    },
    "sklearn_calib": {
        "ieee": "scikit-learn developers, “Probability calibration,” scikit-learn user guide. [Online]. Available: https://scikit-learn.org/stable/modules/calibration.html (accessed {acc}).",
        "bib": "@misc{{sklearn_calib, title={{Probability calibration}}, author={{{{scikit-learn developers}}}}, url={{https://scikit-learn.org/stable/modules/calibration.html}}, note={{Accessed 2026-11-16}}}}",
    },
    "sklearn_gss": {
        "ieee": "scikit-learn developers, “sklearn.model_selection.GroupShuffleSplit,” scikit-learn documentation. [Online]. Available: https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.GroupShuffleSplit.html (accessed {acc}).",
        "bib": "@misc{{sklearn_gss, title={{sklearn.model_selection.GroupShuffleSplit}}, author={{{{scikit-learn developers}}}}, url={{https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.GroupShuffleSplit.html}}, note={{Accessed 2026-11-16}}}}",
    },
    "fastapi": {
        "ieee": "S. Ramírez, “FastAPI,” documentation. [Online]. Available: https://fastapi.tiangolo.com/ (accessed {acc}).",
        "bib": "@misc{{fastapi, title={{FastAPI}}, author={{Ram\\'irez, Sebasti\\'an}}, url={{https://fastapi.tiangolo.com/}}, note={{Accessed 2026-11-16}}}}",
    },
    "postgres": {
        "ieee": "The PostgreSQL Global Development Group, “About PostgreSQL.” [Online]. Available: https://www.postgresql.org/about/ (accessed {acc}).",
        "bib": "@misc{{postgres, title={{About PostgreSQL}}, author={{{{The PostgreSQL Global Development Group}}}}, url={{https://www.postgresql.org/about/}}, note={{Accessed 2026-11-16}}}}",
    },
    "nextjs": {
        "ieee": "Vercel, “Next.js documentation.” [Online]. Available: https://nextjs.org/docs (accessed {acc}).",
        "bib": "@misc{{nextjs, title={{Next.js Documentation}}, author={{{{Vercel}}}}, url={{https://nextjs.org/docs}}, note={{Accessed 2026-11-16}}}}",
    },
    "r3f": {
        "ieee": "Poimandres, “React Three Fiber: Introduction,” documentation. [Online]. Available: https://r3f.docs.pmnd.rs/getting-started/introduction (accessed {acc}).",
        "bib": "@misc{{r3f, title={{React Three Fiber: Introduction}}, author={{{{Poimandres}}}}, url={{https://r3f.docs.pmnd.rs/getting-started/introduction}}, note={{Accessed 2026-11-16}}}}",
    },
    "compose": {
        "ieee": "Docker Inc., “Docker Compose,” Docker documentation. [Online]. Available: https://docs.docker.com/compose/ (accessed {acc}).",
        "bib": "@misc{{compose, title={{Docker Compose}}, author={{{{Docker Inc.}}}}, url={{https://docs.docker.com/compose/}}, note={{Accessed 2026-11-16}}}}",
    },
}

MONTHS = "Jan. Feb. Mar. Apr. May Jun. Jul. Aug. Sep. Oct. Nov. Dec.".split()


def initials(given: str) -> str:
    out = ""
    for token in re.findall(r"[^\W\d_]+|-", given):
        if token == "-":
            out += "-"
        elif token.islower():
            out += token + " "  # Particles such as "da" stay whole.
        else:
            out += token[0] + ". "
    return out.replace(". -", ".-").strip()


def ieee_authors(authors: list[dict]) -> str:
    names = [f"{initials(a.get('given', ''))} {a.get('family', a.get('name', ''))}".strip() for a in authors]
    if len(names) > 6:
        return f"{names[0]} et al."
    if len(names) <= 2:
        return " and ".join(names)
    return ", ".join(names[:-1]) + ", and " + names[-1]


def main() -> None:
    raw = json.load(open(sys.argv[1], encoding="utf8"))
    full = {}
    for doi in raw:
        full[doi] = raw[doi]
    refs = {}
    bib = []
    for key, doi in DOI_KEYS.items():
        m = full[doi]
        authors = m["authors_struct"] if "authors_struct" in m else None
        if authors is None:
            authors = [{"given": " ".join(n.split()[:-1]), "family": n.split()[-1]} for n in m["authors"]]
        title = TITLE_FIX.get(key, html.unescape(m["title"]).replace("‐", "-"))
        container = CONTAINER_FIX.get(key, html.unescape(m["container"]))
        vol, issue, page, year = m["volume"], m["issue"], m["page"], m["year"]
        page = (page or "").replace("-", "–")
        who = ieee_authors(authors)
        if m["type"] == "proceedings-article" or key in ("saxena2008",):
            text = f"{who}, “{title},” in {container}, {year}"
            text += f", pp. {page}" if page else ""
        elif m["type"] == "book-chapter":
            text = f"{who}, “{title},” in {container}, {year}, pp. {page}"
        elif m["type"] == "report":
            text = (f"{who}, “{title},” Nat. Inst. Standards Technol., Gaithersburg, MD, "
                    f"USA, NIST SP 800-82 Rev. 3, Sep. {year}")
        else:
            text = f"{who}, “{title},” {container}"
            text += f", vol. {vol}" if vol else ""
            text += f", no. {issue}" if issue else ""
            if page:
                text += f", {'Art. no. ' + page if page.isdigit() else 'pp. ' + page}"
            text += f", {year}"
        text += f", doi: {doi}."
        refs[key] = {"ieee": text, "doi": doi, "verified": "crossref"}
        family = " and ".join(
            f"{a.get('family', '')}, {a.get('given', '')}".strip(", ") for a in authors
        )
        entry_type = {"proceedings-article": "inproceedings", "book-chapter": "incollection", "report": "techreport"}.get(m["type"], "article")
        venue_field = {"inproceedings": "booktitle", "incollection": "booktitle", "techreport": "institution"}.get(entry_type, "journal")
        fields = [f"title={{{title}}}", f"author={{{family}}}", f"{venue_field}={{{container or 'National Institute of Standards and Technology'}}}", f"year={{{year}}}", f"doi={{{doi}}}"]
        if vol:
            fields.append(f"volume={{{vol}}}")
        if issue:
            fields.append(f"number={{{issue}}}")
        if m["page"]:
            fields.append(f"pages={{{m['page'].replace('-', '--')}}}")
        bib.append(f"@{entry_type}{{{key},\n  " + ",\n  ".join(fields) + "\n}")
    for key, item in WEB.items():
        refs[key] = {"ieee": item["ieee"].format(acc=ACCESSED), "verified": "web"}
        bib.append(item["bib"].format().replace("{{", "{").replace("}}", "}"))
    (HERE / "references.json").write_text(json.dumps(refs, indent=1, ensure_ascii=False), encoding="utf8")
    (HERE.parent / "references.bib").write_text(
        "% Verified bibliography for the Industrial Twin-X project report.\n"
        "% Scholarly entries: metadata from Crossref (api.crossref.org), checked 2026-11-16.\n"
        "% Web entries: pages opened and read on 2026-11-16.\n\n" + "\n\n".join(bib) + "\n",
        encoding="utf8",
    )
    print(len(refs), "references")


if __name__ == "__main__":
    main()
