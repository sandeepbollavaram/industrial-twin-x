# Reference Verification Record

Verification date: 16 November 2026. Every reference in the report was checked before it was cited, as follows.

- **Scholarly sources.** Each DOI was resolved through the Crossref API (api.crossref.org), and authors, title, venue, volume, issue, pages and year were taken from the returned record (see `../build/make_references.py`). The content was then inspected through the abstract (OpenAlex or Semantic Scholar), or, where no abstract was available, the Semantic Scholar summary.
- **Standards and documentation.** Each web page was opened and read.

The "Inspected content" column states exactly what was read. Where only a summary or partial abstract was available, the report cites the source only for statements that the inspected content supports, and wording was revised to fit (see the last section). **Full texts behind paywalls were not read.**

| Key | Source | Metadata check | Inspected content | Used in the report for |
| --- | --- | --- | --- | --- |
| sisinni2018 | Sisinni et al., IEEE TII 2018 | Crossref | Full abstract (OpenAlex) | IIoT vs IoT; industrial challenges |
| xu2014 | Xu, He, Li, IEEE TII 2014 | Crossref | Full abstract | IoT in industries survey |
| alfuqaha2015 | Al-Fuqaha et al., IEEE COMST 2015 | Crossref | Full abstract | IoT enabling technologies and protocols |
| lee2015 | Lee, Bagheri, Kao, Manuf. Letters 2015 | Crossref | Semantic Scholar summary only | 5-level CPS architecture, physical/cyber synchronisation |
| leitao2016 | Leitão, Colombo, Karnouskos, Comput. Ind. 2016 | Crossref | Semantic Scholar summary only | Industrial CPS overview, implementation challenges |
| tao2019 | Tao et al., IEEE TII 2019 | Crossref | Full abstract | DT key components, development, applications |
| kritzinger2018 | Kritzinger et al., IFAC-PapersOnLine 2018 | Crossref | Full abstract | Digital model / shadow / twin classification |
| fuller2020 | Fuller et al., IEEE Access 2020 | Crossref | Abstract | Enabling technologies, open research |
| jones2020 | Jones et al., CIRP JMST 2020 | Crossref | Abstract | 13 characteristics of the DT |
| rasheed2020 | Rasheed, San, Kvamsdal, IEEE Access 2020 | Crossref | Abstract | DT enabled by data and simulators |
| rosen2015 | Rosen et al., IFAC-PapersOnLine 2015 | Crossref | Partial abstract | Autonomy and DTs for manufacturing (general) |
| grieves2017 | Grieves, Vickers, Springer 2017 | Crossref | Semantic Scholar summary only | DT concept across the product lifecycle |
| jardine2006 | Jardine, Lin, Banjevic, MSSP 2006 | Crossref | Semantic Scholar summary only | CBM diagnostics/prognostics review (general) |
| lei2018 | Lei et al., MSSP 2018 | Crossref | Semantic Scholar summary only | Prognostics from data acquisition to RUL |
| carvalho2019 | Carvalho et al., C&IE 2019 | Crossref | Abstract (Semantic Scholar) | ML for PdM; method choice matters |
| zonta2020 | Zonta et al., C&IE 2020 | Crossref | Abstract (Semantic Scholar) | PdM in Industry 4.0 review |
| chandola2009 | Chandola, Banerjee, Kumar, ACM CSUR 2009 | Crossref | Full abstract | Categories and assumptions of anomaly detection |
| liu2008 | Liu, Ting, Zhou, ICDM 2008 | Crossref | Abstract | Isolation Forest principle and reported results |
| breiman2001 | Breiman, Machine Learning 2001 | Crossref | Abstract (Semantic Scholar) | Random forests |
| harris2020 | Harris et al., Nature 2020 | Crossref | Abstract | NumPy |
| hunter2007 | Hunter, CiSE 2007 | Crossref | Abstract | Matplotlib |
| niculescu2005 | Niculescu-Mizil, Caruana, ICML 2005 | Crossref | Abstract | Probability distortion; Platt and isotonic calibration |
| kaufman2012 | Kaufman et al., ACM TKDD 2012 | Crossref | Abstract | Leakage |
| roberts2017 | Roberts et al., Ecography 2017 | Crossref | Abstract | Structured cross-validation |
| saxena2008 | Saxena et al., PHM 2008 | Crossref | Abstract | Simulated run-to-failure with exponential damage |
| boglietti2009 | Boglietti et al., IEEE TIE 2009 | Crossref | Abstract | Lumped-parameter, FEA, CFD thermal analysis |
| isermann2005 | Isermann, Annu. Rev. Control 2005 | Crossref | Semantic Scholar summary only | Model-based fault detection (general) |
| venkat2003 | Venkatasubramanian et al., Comput. Chem. Eng. 2003 | Crossref | Semantic Scholar summary only | Three categories of FDD methods; Part I scope |
| ge2017 | Ge et al., IEEE Access 2017 | Crossref | Abstract | ML in the process industry |
| shi2016 | Shi et al., IEEE IoT J 2016 | Crossref | Abstract | Edge computing definition and motivations |
| satya2017 | Satyanarayanan, Computer 2017 | Crossref | Abstract | Edge computing masks transient cloud outages |
| humayed2017 | Humayed et al., IEEE IoT J 2017 | Crossref | Abstract (Semantic Scholar) | CPS security framework |
| cardenas2011 | Cárdenas et al., ASIACCS 2011 | Crossref | Partial abstract and full title | Risk assessment, detection, response for process control attacks |
| liu2009 | Liu, Ning, Reiter, CCS 2009 | Crossref | Partial abstract | False data injection against state estimation |
| langner2011 | Langner, IEEE S&P 2011 | Crossref | Abstract | Stuxnet aimed at physical destruction |
| hunkeler2008 | Hunkeler, Truong, Stanford-Clark, COMSWARE 2008 | Crossref | Abstract | MQTT-S for wireless sensor networks |
| light2017 | Light, JOSS 2017 | Crossref | Abstract | Eclipse Mosquitto |
| nist80082 | Stouffer et al., NIST SP 800-82r3, 2023 | Crossref and the NIST CSRC page | Abstract; CSRC page | OT security guidance |
| mqtt311 | OASIS MQTT 3.1.1, 2014 | Page opened | Abstract, sections 3.1.2.5, 3.1.2.10, 4.7.1 | QoS levels, keep-alive, Last Will, wildcards |
| mqtt5 | OASIS MQTT 5.0, 2019 | Page opened | Title, status, editors, introduction | MQTT description |
| pedregosa2011 | Pedregosa et al., JMLR 2011 | JMLR page | Abstract | scikit-learn |
| isa62443 | ISA/IEC 62443 series | ISA page opened | Page text | IACS security standards |
| opcua | OPC Foundation, OPC UA | Page opened | Page text | OPC UA description (future work) |
| ditto | Eclipse Ditto overview | Page opened | Page text | Cached last-known state of Things |
| awsshadow | AWS IoT Device Shadow documents | Page opened | Full page | Desired, reported, delta |
| simpy | SimPy documentation | Page opened | Page text | Process-based discrete-event simulation |
| paho | Eclipse Paho Python client docs | Page opened | loop_start, reconnect, queue, protocol | Client behaviour |
| sklearn_iforest | scikit-learn IsolationForest docs | Page opened | Full page | score_samples sign, contamination |
| sklearn_calib | scikit-learn calibration guide | Page opened | Full page | Reliability diagrams, isotonic overfitting |
| sklearn_gss | scikit-learn GroupShuffleSplit docs | Page opened | Full page | Group-based splitting |
| fastapi | FastAPI documentation | Page opened | Home page | Self-description |
| postgres | PostgreSQL About page | Page opened | Page text | Self-description |
| nextjs | Next.js documentation | Page opened | Docs home | Self-description |
| r3f | React Three Fiber docs | Page opened | Introduction | Self-description |
| compose | Docker Compose docs | Page opened | Overview | Self-description |

## Sources considered and not used

- **ISO 20816-1 (vibration evaluation).** The ISO page returned HTTP 403, so the standard could not be inspected. The report therefore does not cite it, and states that its vibration limits are simulation parameters, not standard values.
- **Liu, Ting and Zhou 2012, "Isolation-based anomaly detection" (TKDD).** Listed by the scikit-learn documentation, but not needed.

## Wording revised after inspection

Draft sentences that went beyond the inspected content were revised before the final build:

- Jardine et al.: removed the specific three-step description of CBM.
- Lei et al.: removed the description of health-indicator construction and degradation-stage division.
- Tao et al.: removed the list of four DT components.
- Al-Fuqaha et al.: removed the statement that the survey names MQTT.
- Rosen et al.: "argued that autonomy depends on DTs" became "discussed the importance of".
- Chandola et al.: removed the definition of statistical techniques attributed to the survey.
- Liu, Ning and Reiter: removed "when the attacker knows the system configuration".
- Cárdenas et al.: removed attribution of "model-based detection".
- Isermann; Venkatasubramanian et al.: removed method details not in the inspected summaries.
- MQTT wildcards: verified in section 4.7.1 of the standard, then cited.
