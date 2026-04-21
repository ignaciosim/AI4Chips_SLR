"""
slr_ontology.py — Single source of truth for the silicon lifecycle SLR domain.

This module defines the ontology that all pipeline stages draw from:
  - Lifecycle phases and their Scopus query vocabulary
  - AI/ML method taxonomy (replaces post_process_ai_methods.AI_METHODS)
  - Chip design task taxonomy
  - Hardware artifact taxonomy (chips-for-AI signals)
  - AI workload taxonomy (chips-for-AI signals)
  - Chip anchor vocabulary for domain filtering
  - Scopus query generation helpers

Other scripts import from here instead of maintaining parallel vocab lists.

Architecture:
  slr_ontology.py          ← YOU ARE HERE (shared knowledge)
  fetch_scopus.py          ← reads ontology for query building
  merge_scopus.py          ← pure plumbing, no domain knowledge
  classify_scopus.py       ← reads ontology for entity extraction + directionality
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Set


# =============================================================================
# LIFECYCLE PHASES
# Each phase has:
#   - scopus_terms: vocabulary for Scopus TITLE-ABS-KEY queries
#   - description: human-readable summary
# =============================================================================

@dataclass
class LifecyclePhase:
    key: str
    label: str
    description: str
    scopus_terms: str  # Scopus boolean query fragment


PHASES: Dict[str, LifecyclePhase] = {
    "design": LifecyclePhase(
        key="design",
        label="Design",
        description="RTL through physical design: synthesis, placement, routing, timing, analog design.",
        scopus_terms=(
            '"electronic design automation" OR "EDA" OR "Schematic" OR "schematic" OR '
            '"high-level synthesis" OR HLS OR SystemC OR '
            '"standard cell" OR "cell placement" OR "analog design" OR '
            'floorplan OR floorplanning OR '
            '"place and route" OR PnR OR Analog OR analog OR '
            'DRC OR PDK OR LVS'
        ),
    ),
    "fabrication": LifecyclePhase(
        key="fabrication",
        label="Fabrication",
        description="Wafer-level manufacturing: lithography, yield, defects, process control.",
        scopus_terms=(
            '"yield" OR "wafer" OR "die yield" OR '
            '"defect detection" OR "defect classification" OR '
            'metrology OR "process variation" OR '
            'photolithography OR "layer deposition" OR ALD OR OPC OR '
            '"critical dimension" OR '
            'CMP'
        ),
    ),
    "packaging": LifecyclePhase(
        key="packaging",
        label="Packaging & Assembly",
        description="Die-level and multi-die integration: chiplets, interposers, 3D stacking.",
        scopus_terms=(
            'chiplet OR interposer OR TSV OR "Through-silicon via" OR UCIe OR HBM OR '
            '"3D integration" OR "advanced packaging" OR "3D IC" OR "2.5D IC" OR '
            '"Heterogeneous" OR "3DIC" OR '
            '"thermal management"'
        ),
    ),
    "transit": LifecyclePhase(
        key="transit",
        label="Transit",
        description="Foundry-to-system: post-fab test, supply chain integrity, authentication, binning.",
        scopus_terms=(
            '"supply chain" OR "semiconductor supply chain" OR '
            '"counterfeit" OR "IC counterfeit" OR "counterfeit detection" OR '
            '"hardware authentication" OR "physically unclonable function" OR PUF OR '
            '"chip provenance" OR "chain of custody" OR traceability OR '
            '"burn-in" OR "system-level test" OR SLT OR '
            '"final test" OR "package test" OR "wafer probe" OR "wafer sort" OR '
            '"known good die" OR KGD OR '
            '"hardware trojan" OR "trojan detection" OR '
            '"binning" OR "speed binning"'
        ),
    ),
    "in_field": LifecyclePhase(
        key="in_field",
        label="In-Field Operation",
        description="Post-deployment: reliability, aging, security, field failures.",
        scopus_terms=(
            '"post-silicon" OR "in-field" OR "field failure" OR telemetry OR '
            'reliability OR aging OR wearout OR silent OR radiation OR CEE OR SEE OR '
            'BTI OR HCI OR electromigration OR SDE OR SDC OR '
            '"anomaly detection" OR "single-event effect" OR "predictive maintenance"'
        ),
    ),
    "disposal": LifecyclePhase(
        key="disposal",
        label="Disposal",
        description="End-of-life: e-waste, recycling, decommissioning, secure data destruction.",
        scopus_terms=(
            '"electronic waste" OR "e-waste" OR WEEE OR '
            '"end-of-life" OR "end of life electronics" OR '
            '"electronics recycling" OR "semiconductor recycling" OR '
            '"circular economy electronics" OR "material recovery" OR '
            '"urban mining" OR '
            '"decommissioning" OR demanufacturing OR dismantling OR '
            '"secure erasure" OR "data sanitization" OR "cryptographic erasure" OR '
            '"RoHS" OR "hazardous substances"'
        ),
    ),
}


# =============================================================================
# CHIP ANCHOR — domain filter ensuring results are about IC/EDA, not off-domain
# Used in Scopus queries as: AND TITLE-ABS-KEY({CHIP_ANCHOR})
# =============================================================================

CHIP_ANCHOR = (
    '"integrated circuit" OR "IC design" OR CMOS OR VLSI OR '
    '"standard cell" OR "cell library" OR netlist OR '
    '"physical design" OR "System Verilog" OR "place and route" OR '
    '"static timing analysis" OR "timing closure" OR '
    '"clock tree" OR TCAD OR CTS OR '
    'layout OR "layout synthesis" OR "simulation" OR '
    'lithography OR mask OR "design rule" OR DRC OR LVS OR '
    '"EDA" OR "electronic design automation"'
)


# =============================================================================
# AI UMBRELLA — broad AI terms for --ai_focus filtering in Scopus queries
# =============================================================================

AI_UMBRELLA = (
    '"artificial intelligence" OR "machine learning" OR "deep learning" OR '
    '"neural network" OR "reinforcement learning" OR "graph neural network"'
)


# =============================================================================
# AI METHOD TAXONOMY
# Used for:
#   1. Entity extraction in the classifier (detecting AI-as-tool)
#   2. Method tagging / pivot tables (replaces post_process_ai_methods.py)
#
# Each method has:
#   - scopus_surface_forms: strings to match in title/abstract (lowercase)
#   - label: human-readable name
# =============================================================================

@dataclass
class OntologyClass:
    """A class in the ontology with associated lexical anchors."""
    key: str
    label: str
    surface_forms: List[str]
    parent: str = ""


# ---- AI Methods (tool / technique) ----

AI_METHODS: Dict[str, OntologyClass] = {
    "llm_foundation_models": OntologyClass(
        key="llm_foundation_models",
        label="LLM / Foundation Models",
        surface_forms=[
            "large language model", "large-language model", "language model", "llm",
            "foundation model", "foundation models",
            "generative ai", "generative model",
            "bert", "gpt", "chatgpt", "t5", "llama", "falcon", "mistral",
            "prompt engineering", "prompting", "prompt tuning",
            "instruction tuning", "in-context learning", "few-shot",
            "pre-trained language model", "retrieval augmented", "rag",
        ],
        parent="deep_learning",
    ),
    "deep_learning": OntologyClass(
        key="deep_learning",
        label="Deep Learning",
        surface_forms=[
            "deep learning", "deep neural", "deep neural network", "dnn",
            "neural network", "neural networks",
            "cnn", "convolutional neural", "rnn", "lstm",
            "autoencoder", "variational autoencoder", "vae",
            "representation learning", "self-supervised learning",
            "contrastive learning",
            "back-propagation", "backpropagation",
        ],
    ),
    "graph_neural_networks": OntologyClass(
        key="graph_neural_networks",
        label="Graph Neural Networks",
        surface_forms=[
            "graph neural", "graph neural network", "gnn",
            "message passing neural", "graph convolution",
            "graph embedding", "gcn",
            "graph learning", "graph neural process",
        ],
    ),
    "reinforcement_learning": OntologyClass(
        key="reinforcement_learning",
        label="Reinforcement Learning",
        surface_forms=[
            "reinforcement learning", "policy gradient",
            "q-learning", "actor critic", "markov decision",
            "deep q network", "dqn",
        ],
    ),
    "bayesian_probabilistic": OntologyClass(
        key="bayesian_probabilistic",
        label="Bayesian / Probabilistic",
        surface_forms=[
            "bayesian", "gaussian process", "probabilistic model",
            "variational inference", "uncertainty quantification",
            "bayesian optimization", "surrogate model",
        ],
    ),
    "evolutionary_optimization": OntologyClass(
        key="evolutionary_optimization",
        label="Evolutionary / Metaheuristic Optimization",
        surface_forms=[
            "genetic algorithm", "evolutionary algorithm",
            "particle swarm", "simulated annealing",
            "differential evolution", "cma-es",
            "evolutionary", "nsga",
        ],
    ),
    "classical_ml": OntologyClass(
        key="classical_ml",
        label="Classical ML",
        surface_forms=[
            "support vector", "svm", "random forest", "xgboost",
            "gradient boosting", "decision tree",
            "k-means", "clustering",
            "logistic regression", "linear regression",
            "machine learning",
        ],
    ),
    "symbolic_reasoning": OntologyClass(
        key="symbolic_reasoning",
        label="Symbolic Reasoning",
        surface_forms=[
            "symbolic", "logic programming",
            "satisfiability", "sat solver",
            "constraint programming", "ilp", "smt",
        ],
    ),
    "transfer_learning": OntologyClass(
        key="transfer_learning",
        label="Transfer Learning",
        surface_forms=[
            "transfer learning", "domain adaptation",
        ],
    ),
    "anomaly_detection": OntologyClass(
        key="anomaly_detection",
        label="Anomaly Detection",
        surface_forms=[
            "anomaly detection", "changepoint", "outlier detection",
        ],
    ),
    "generative_adversarial": OntologyClass(
        key="generative_adversarial",
        label="Generative Adversarial Networks",
        surface_forms=[
            "gan", "generative adversarial", "adversarial network",
        ],
    ),
    "general_ml_signals": OntologyClass(
        key="general_ml_signals",
        label="General ML Signals",
        surface_forms=[
            "ml-based", "ml-guided", "learning-based", "learning-guided",
            "data-driven", "prediction model", "predictive model",
            "trained model", "ai-driven", "ai-based", "ai-assisted",
            "ai-guided",
            # Virtual metrology is inherently ML-based (predicting measurements from process data)
            "virtual metrology",
        ],
    ),
}


# ---- Chip Design Tasks (target / problem domain for AI-for-chips) ----

CHIP_DESIGN_TASKS: Dict[str, OntologyClass] = {
    "placement": OntologyClass(
        key="placement", label="Placement",
        surface_forms=[
            "placement", "place-and-route", "place and route", "p&r",
            "floorplanning", "floorplan", "floor plan", "macro placement",
            "cell placement", "global placement",
        ],
    ),
    "routing": OntologyClass(
        key="routing", label="Routing",
        surface_forms=[
            "routing", "global routing", "detailed routing",
            "wire routing", "pathfinding", "interconnect optimization",
            "congestion", "routability",
        ],
    ),
    "timing_analysis": OntologyClass(
        key="timing_analysis", label="Timing Analysis",
        surface_forms=[
            "timing analysis", "timing closure", "timing optimization",
            "static timing", "timing prediction", "delay prediction",
            "delay estimation", "slack", "timing-driven",
            "timing model", "path delay",
        ],
    ),
    "logic_synthesis": OntologyClass(
        key="logic_synthesis", label="Logic Synthesis",
        surface_forms=[
            # Core synthesis terms
            "logic synthesis", "high-level synthesis", "hls",
            "rtl", "logic optimization", "technology mapping",
            # HDL languages (indicate RTL/logic design tasks)
            "verilog", "vhdl", "systemverilog",
            "hardware description language", "hdl",
            # RTL/code generation
            "rtl generation", "rtl synthesis", "code generation",
            "design automation", "eda",
            # LLM-for-EDA specific patterns
            "eda assistant", "eda agent", "design assistant",
            # Specification-to-RTL
            "spec-to-rtl", "specification to rtl",
            # Gate/cell sizing
            "gate sizing", "cell sizing", "logic circuit",
        ],
    ),
    "power_analysis": OntologyClass(
        key="power_analysis", label="Power Analysis",
        surface_forms=[
            "power estimation", "power prediction", "power optimization",
            "ir drop", "power grid", "voltage drop", "power delivery",
            "pdn", "power integrity", "dynamic power",
        ],
    ),
    "design_space_exploration": OntologyClass(
        key="design_space_exploration", label="Design Space Exploration",
        surface_forms=[
            "design space exploration", "dse", "pareto",
            "design optimization", "co-optimization",
        ],
    ),
    "analog_circuit_design": OntologyClass(
        key="analog_circuit_design", label="Analog Circuit Design",
        surface_forms=[
            "analog design", "analog circuit", "adc", "dac",
            "analog-to-digital", "pll", "amplifier design",
            "op-amp", "analog layout", "transistor sizing",
            # Extended terms for AI-assisted analog/RF design
            "circuit optimization", "circuit synthesis", "analog sizing",
            "ic sizing", "rf circuit", "mixed-signal circuit",
            "operational amplifier", "ota", "lna", "vco",
            "analog ic", "rf ic", "mixed-signal ic",
        ],
    ),
    "verification": OntologyClass(
        key="verification", label="Verification",
        surface_forms=[
            "verification", "formal verification", "assertion",
            "bug prediction", "coverage prediction", "test coverage",
            "simulation acceleration",
            # IC/chip test terms
            "ic test", "chip test", "soc test", "wafer test",
            "post-silicon", "postsilicon", "debug",
        ],
    ),
    "calibration": OntologyClass(
        key="calibration", label="Calibration",
        surface_forms=[
            "calibration", "background calibration", "equalization",
            "signal integrity", "metamodeling",
            # Device/model parameter extraction
            "parameter extraction", "model extraction",
            "device modeling", "compact model", "spice model",
            # Performance modeling and characterization
            "circuit modeling", "performance modeling",
            "device characterization", "ic characterization",
            "circuit performance", "mosfet model",
        ],
    ),
    "lithography_optimization": OntologyClass(
        key="lithography_optimization", label="Lithography Optimization",
        surface_forms=[
            "lithography", "opc", "optical proximity correction",
            "mask optimization", "mask synthesis",
            "source mask optimization", "smo",
            # Assist features and ILT
            "assist feature", "sraf", "subresolution assist",
            "inverse lithography", "ilt",
            "etch proximity", "etch correction",
        ],
    ),
    "hotspot_detection": OntologyClass(
        key="hotspot_detection", label="Hotspot Detection",
        surface_forms=[
            "hotspot detection", "hotspot", "lithography hotspot",
            "via failure", "pattern detection",
        ],
    ),
    "defect_detection": OntologyClass(
        key="defect_detection", label="Defect Detection",
        surface_forms=[
            "defect detection", "defect classification",
            "defect inspection", "anomaly detection in wafer",
            "adversarial defect",
            # Layout/IC defect analysis
            "layout analysis", "ic-defect", "systematic defect",
            "defect identification", "latent defect",
        ],
    ),
    "yield_prediction": OntologyClass(
        key="yield_prediction", label="Yield Prediction",
        surface_forms=[
            "yield prediction", "yield estimation", "yield improvement",
            "yield analysis", "yield optimization", "yield enhancement",
            "yield learning", "yield model",
        ],
    ),
    "wafer_map_analysis": OntologyClass(
        key="wafer_map_analysis", label="Wafer Map Analysis",
        surface_forms=[
            "wafer map", "wafer-level", "wafer bin map",
            "wafer map yield",
        ],
    ),
    "process_optimization": OntologyClass(
        key="process_optimization", label="Process Optimization",
        surface_forms=[
            # Existing terms
            "cmp", "chemical mechanical", "etch optimization",
            "process optimization", "process control",
            "process variation", "dtco",
            # Deposition processes
            "ald", "atomic layer deposition", "atomic layer",
            "cvd", "chemical vapor deposition",
            "pecvd", "mocvd", "lpcvd",
            "pvd", "physical vapor deposition", "sputtering",
            "thin film", "film deposition", "film thickness",
            "deposition process", "deposition control",
            "epitaxy", "epitaxial growth",
            # Metrology
            "virtual metrology", "metrology",
            "recipe optimization",
        ],
    ),
    "test_generation": OntologyClass(
        key="test_generation", label="Test Generation",
        surface_forms=[
            "test generation", "atpg", "test pattern",
            "test compaction", "test point insertion",
            "test scheduling",
        ],
    ),
    "fault_diagnosis": OntologyClass(
        key="fault_diagnosis", label="Fault Diagnosis",
        surface_forms=[
            "fault diagnosis", "fault localization", "diagnosis",
            "root cause", "failure analysis",
        ],
    ),
    "reliability_analysis": OntologyClass(
        key="reliability_analysis", label="Reliability Analysis",
        surface_forms=[
            # Traditional wear-out / aging mechanisms
            "reliability", "aging", "degradation", "electromigration",
            "bti", "nbti", "hci", "tddb", "wear-out",
            "stress estimation", "lifetime prediction",
            # Soft errors / silent data errors / transient faults
            "soft error", "soft-error", "seu", "single event upset",
            "single-event upset", "silent data", "sdc", "sde",
            "transient fault", "bit flip", "bit-flip",
            "critical flip-flop", "fault injection", "fault tolerance",
            "radiation effect", "cosmic ray", "alpha particle",
            "failure rate", "error rate", "fit rate",
        ],
    ),
    "thermal_management": OntologyClass(
        key="thermal_management", label="Thermal Management",
        surface_forms=[
            "thermal management", "thermal-aware", "thermal estimation",
            "temperature prediction", "thermal analysis", "thermal model",
        ],
    ),
    "security_analysis": OntologyClass(
        key="security_analysis", label="Security Analysis",
        surface_forms=[
            "hardware trojan", "trojan detection", "counterfeit",
            "recycled", "side-channel", "puf",
            "hardware security", "ic protection",
        ],
    ),
}


# ---- Hardware Artifacts (chips-for-AI signal: the chip IS the product) ----

HW_ARTIFACTS: Dict[str, OntologyClass] = {
    "neural_accelerator": OntologyClass(
        key="neural_accelerator", label="Neural Network Accelerator",
        surface_forms=[
            "accelerator for", "neural accelerator", "dnn accelerator",
            "cnn accelerator", "inference accelerator",
            "hardware accelerator for neural",
            "hardware acceleration of convolutional",
            "hardware acceleration of deep",
            "neural processing unit",
        ],
    ),
    "in_memory_computing": OntologyClass(
        key="in_memory_computing", label="In-Memory Computing Architecture",
        surface_forms=[
            "in-memory computing", "processing-in-memory", "pim",
            "compute-in-memory", "cim", "analog computing",
            "dot-product engine", "crossbar-based",
            "sram-based computing", "memristive crossbar",
            "resistive crossbar", "reram-based", "rram-based",
        ],
    ),
    "neuromorphic_chip": OntologyClass(
        key="neuromorphic_chip", label="Neuromorphic Chip",
        surface_forms=[
            "neuromorphic", "spiking neural network",
            "spike-based", "neurosynaptic",
        ],
    ),
    "fpga_accelerator": OntologyClass(
        key="fpga_accelerator", label="FPGA-based Accelerator",
        surface_forms=[
            "fpga-based accelerator", "fpga accelerator",
            "fpga-based inference", "fpga-based neural",
            "overlay on fpga",
        ],
    ),
    "specialized_architecture": OntologyClass(
        key="specialized_architecture", label="Specialized AI Architecture",
        surface_forms=[
            "systolic array", "dataflow architecture",
            "reconfigurable accelerator", "mixed-signal neuron",
            "stochastic computing-based inference",
            "computing engine using",
        ],
    ),
}


# ---- AI Workloads (chips-for-AI signal: the chip runs THIS) ----

AI_WORKLOADS: Dict[str, OntologyClass] = {
    "dnn_inference": OntologyClass(
        key="dnn_inference", label="DNN Inference",
        surface_forms=[
            "dnn inference", "deep neural network inference",
            "cnn inference", "inference framework",
            "inference on edge", "inference pipeline",
            "inference acceleration", "inference accuracy",
            "inference on fpga",
        ],
    ),
    "dnn_training": OntologyClass(
        key="dnn_training", label="DNN Training",
        surface_forms=[
            "dnn training", "neural network training",
            "training acceleration", "training workload",
        ],
    ),
    "transformer_inference": OntologyClass(
        key="transformer_inference", label="Transformer Inference",
        surface_forms=[
            "vision transformer", "vision-transformer", "self-attention",
            "transformer inference", "attention mechanism",
        ],
    ),
    "spiking_execution": OntologyClass(
        key="spiking_execution", label="Spiking NN Execution",
        surface_forms=[
            "spiking neural network execution",
            "snn inference", "snn on chip",
        ],
    ),
    "generic_ai_workload": OntologyClass(
        key="generic_ai_workload", label="Generic AI Workload",
        surface_forms=[
            "deep learning workload", "machine learning workload",
            "ai workload", "neural network execution",
            "convolutional layer", "mac operation",
            "multiply-and-accumulate",
        ],
    ),
}


# =============================================================================
# CHIPS-FOR-AI HEURISTIC PHRASES
# Fallback phrases that signal chips-for-AI even when no artifact/workload
# class matches cleanly.
# =============================================================================

CHIPS_FOR_AI_HEURISTIC_PHRASES = [
    "energy-efficient", "energy efficient",
    "sparse neural", "sparse cnn", "sparse dnn",
    "bit-serial", "bit stuffing",
    "weight sparsity", "weight density",
    "quantization", "quantized neural",
    "binary neural network",
    "multicast mechanism for",
    "noc-based deep neural", "noc-based dnn",
    "fpga-based cnn", "fpga-based dnn", "fpga-based neural",
    "fpga-based spiking",
    "chiplet-based dnn", "chiplet-based accelerator",
    "interposer based", "interposer-based",
    "co-design for", "co-design platform for",
    "end-to-end compiler",
    "photonic interconnect",
]

# AI-related keywords that combine with the above to confirm chips-for-AI
CHIPS_FOR_AI_CONFIRM_KEYWORDS = [
    "neural", "dnn", "cnn", "inference", "accelerat",
]


# =============================================================================
# HELPER: match surface forms against text
# =============================================================================

def match_ontology_classes(
    text: str,
    class_dict: Dict[str, OntologyClass],
) -> Dict[str, List[str]]:
    """
    Match a text string against all classes in a dict.
    Returns {class_key: [matched_surface_form, ...]} for classes with hits.
    """
    text_lower = text.lower()
    hits: Dict[str, List[str]] = {}
    for key, cls in class_dict.items():
        for form in cls.surface_forms:
            if form.lower() in text_lower:
                hits.setdefault(key, []).append(form)
                break  # one match per class is sufficient
    return hits


def detect_ai_methods(text: str, keep_dl_with_llm: bool = False) -> Set[str]:
    """
    Multi-label AI method detection. Drop-in replacement for
    post_process_ai_methods.detect_methods().
    """
    hits = match_ontology_classes(text, AI_METHODS)
    method_keys = set(hits.keys())

    # De-overlap: if LLM detected, optionally remove generic deep_learning
    if (not keep_dl_with_llm
            and "llm_foundation_models" in method_keys
            and "deep_learning" in method_keys):
        method_keys.discard("deep_learning")

    return method_keys


# =============================================================================
# HELPER: build Scopus query from ontology
# =============================================================================

def build_scopus_query(
    stage_key: str,
    year: int,
    ai_focus: bool = False,
    venues: List[str] | None = None,
) -> str:
    """Build a Scopus boolean query from ontology-defined vocabulary."""
    phase = PHASES[stage_key]

    q = (
        f"TITLE-ABS-KEY({phase.scopus_terms}) "
        f"AND TITLE-ABS-KEY({CHIP_ANCHOR}) "
        f"AND PUBYEAR = {year}"
    )

    if ai_focus:
        q = f"{q} AND TITLE-ABS-KEY({AI_UMBRELLA})"

    if venues:
        ors = " OR ".join(
            [f'SRCTITLE("{v.replace(chr(34), chr(39))}")' for v in venues]
        )
        q += f" AND ({ors})"

    q += " AND SRCTYPE(j) AND DOCTYPE(ar)"
    return q


# =============================================================================
# OWL EXPORT (optional — generates the formal OWL file from this module)
# =============================================================================

def export_owl(path: str = "silicon_lifecycle_ontology.owl") -> None:
    """Generate an OWL/RDF-XML file from the Python-defined ontology.

    Produces Protégé 5.x-compatible OWL/RDF-XML with:
    - UTF-8 encoding declaration
    - xml:base and default namespace on rdf:RDF root
    - Fully-qualified absolute IRIs
    - Proper XML escaping via ElementTree
    """
    import xml.etree.ElementTree as ET
    import re

    # -- Namespace URIs -------------------------------------------------------
    ONT  = "http://silicon-lifecycle.org/ontology#"
    OWL  = "http://www.w3.org/2002/07/owl#"
    RDF  = "http://www.w3.org/1999/02/22/rdf-syntax-ns#"
    RDFS = "http://www.w3.org/2000/01/rdf-schema#"
    XSD  = "http://www.w3.org/2001/XMLSchema#"

    def iri(fragment: str) -> str:
        return f"{ONT}{fragment}"

    # Register namespace prefixes for serialization
    ET.register_namespace("owl",  OWL)
    ET.register_namespace("rdf",  RDF)
    ET.register_namespace("rdfs", RDFS)
    ET.register_namespace("xsd",  XSD)

    def rdf(local):  return f"{{{RDF}}}{local}"
    def rdfs(local): return f"{{{RDFS}}}{local}"
    def owl(local):  return f"{{{OWL}}}{local}"

    # -- Build full tree under rdf:RDF root -----------------------------------
    root = ET.Element(rdf("RDF"))

    # owl:Ontology
    ontology = ET.SubElement(root, owl("Ontology"))
    ontology.set(rdf("about"), ONT.rstrip("#"))
    el = ET.SubElement(ontology, rdfs("label"))
    el.text = "Silicon Lifecycle Ontology for SLR Classification"
    el = ET.SubElement(ontology, owl("versionInfo"))
    el.text = "0.3.0"

    # owl:ObjectProperty
    for name, dom, rng in [
        ("methodAppliedToTask",          "AIMethod",        "ChipDesignTask"),
        ("artifactOptimizedForWorkload", "HardwareArtifact","AIWorkload"),
    ]:
        prop = ET.SubElement(root, owl("ObjectProperty"))
        prop.set(rdf("about"), iri(name))
        d = ET.SubElement(prop, rdfs("domain"))
        d.set(rdf("resource"), iri(dom))
        r = ET.SubElement(prop, rdfs("range"))
        r.set(rdf("resource"), iri(rng))

    # owl:Class — top-level
    for about, desc in [
        ("AIMethod",         "AI/ML technique used as a tool"),
        ("ChipDesignTask",   "Engineering task in the silicon lifecycle"),
        ("HardwareArtifact", "Chip architecture or component (product)"),
        ("AIWorkload",       "Computational task a chip is designed to run"),
        ("LifecyclePhase",   "Phase in the silicon product lifecycle"),
    ]:
        cls = ET.SubElement(root, owl("Class"))
        cls.set(rdf("about"), iri(about))
        el = ET.SubElement(cls, rdfs("label"))
        el.text = about
        el = ET.SubElement(cls, rdfs("comment"))
        el.text = desc

    # owl:Class — subclasses
    for d, parent in [
        (AI_METHODS,        "AIMethod"),
        (CHIP_DESIGN_TASKS, "ChipDesignTask"),
        (HW_ARTIFACTS,      "HardwareArtifact"),
        (AI_WORKLOADS,      "AIWorkload"),
    ]:
        for key, entry in d.items():
            cls = ET.SubElement(root, owl("Class"))
            cls.set(rdf("about"), iri(key))
            sub = ET.SubElement(cls, rdfs("subClassOf"))
            sub.set(rdf("resource"), iri(parent))
            el = ET.SubElement(cls, rdfs("label"))
            el.text = entry.label

    # owl:NamedIndividual — lifecycle phases
    for phase in PHASES.values():
        ind = ET.SubElement(root, owl("NamedIndividual"))
        ind.set(rdf("about"), iri(phase.key))
        typ = ET.SubElement(ind, rdf("type"))
        typ.set(rdf("resource"), iri("LifecyclePhase"))
        el = ET.SubElement(ind, rdfs("label"))
        el.text = phase.label

    # -- Serialize ------------------------------------------------------------
    ET.indent(root, space="    ")
    raw = ET.tostring(root, encoding="unicode", xml_declaration=False)

    # Post-process: replace the root <rdf:RDF ...> open tag with one that
    # includes xml:base and the default namespace (xmlns="..."), which
    # ET.register_namespace("", ...) handles inconsistently.
    # The ET-generated tag will look like:
    #   <rdf:RDF xmlns:owl="..." xmlns:rdf="..." xmlns:rdfs="...">
    # We replace it with the Protégé-standard form.
    raw = re.sub(
        r'<rdf:RDF[^>]*>',
        '<rdf:RDF xmlns="' + ONT + '"\n'
        '     xml:base="' + ONT.rstrip("#") + '"\n'
        '     xmlns:owl="' + OWL + '"\n'
        '     xmlns:rdf="' + RDF + '"\n'
        '     xmlns:rdfs="' + RDFS + '"\n'
        '     xmlns:xsd="' + XSD + '">',
        raw,
        count=1
    )

    # Use Protege's exact XML declaration format (no encoding attribute)
    doc = f'<?xml version="1.0"?>\n{raw}\n'

    with open(path, "w", encoding="utf-8") as f:
        f.write(doc)

    print(f"Wrote OWL ontology: {path}")


# =============================================================================
# CLI: export OWL when run directly
# =============================================================================

if __name__ == "__main__":
    export_owl()
    print(f"\nOntology summary:")
    print(f"  Lifecycle phases:    {len(PHASES)}")
    print(f"  AI method classes:   {len(AI_METHODS)}")
    print(f"  Chip design tasks:   {len(CHIP_DESIGN_TASKS)}")
    print(f"  Hardware artifacts:  {len(HW_ARTIFACTS)}")
    print(f"  AI workloads:        {len(AI_WORKLOADS)}")
    total_forms = sum(
        len(c.surface_forms)
        for d in [AI_METHODS, CHIP_DESIGN_TASKS, HW_ARTIFACTS, AI_WORKLOADS]
        for c in d.values()
    )
    print(f"  Total surface forms: {total_forms}")
