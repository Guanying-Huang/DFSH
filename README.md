# Comprehensive Resources for DFSH Decision-Support System

This repository contains the consolidated implementation details supporting the findings of the study. The repository encompasses the source code for the IFC2KG algorithm, the prompt scripts for the LLM-driven regulatory KG construction, the pre-defined Python functions for Spatial KG retrieval, and the prompt scripts for each collaborative agent.

## 1. Spatial Knowledge Graph Construction

This module contains the source code for constructing a hierarchical Spatial Knowledge Graph from as-built BIM data in IFC format. To enhance code readability and execution efficiency, the entire extraction and construction pipeline has been consolidated into a single comprehensive script (e.g., `ifc2kg_pipeline.py`) located in the root directory of this repository.

### Semantic Schema and Topology
The graph extends fundamental IFC entity mappings by introducing a global context and external environment anchor, enabling the multi-agent system (MAS) to effectively reason about holistic project connectivity.

### Graph Characteristics
* **Total Nodes**: 361
* **Total Relationships**: 517

### Entity Types
* **Project**: The overarching global node representing the case project.
* **Space**: Internal spaces (mapped from `IfcSpace`) and one explicit Outdoor anchor node.
* **Boundary**: Mapped from `IfcWall`, `IfcColumn`, `IfcCovering`, `IfcSlab`.
* **Connection**: Mapped from `IfcWindow`, `IfcDoor`.
* **Equipment**: Mapped from `IfcBuildingElementProxy`.
* **MEP Component**: Mapped from `IfcAirTerminal`, `IfcLightFixture`, `IfcSanitaryTerminal`.

### Relationship Types
* **Has**: Connects `Project` to various `Space` nodes.
* **Bounds**: Links `Boundary` to `Space`.
* **Connects**: Links `Connection` to `Space`.
* **Hosts**: Links `Boundary` to `Connection`.
* **Contains**: Links `Space` to `Equipment`.
* **Serves**: Links `MEP Component` to `Space`.

### Implementation Phases and Functional Descriptions
Reflecting its actual computational workflow, the execution logic of the consolidated `ifc2kg_pipeline.py` script is architected into three specific phases, as formally described in the manuscript:

* **Phase 1: Initialization and Parsing**: The algorithm first parses the hierarchical topology of the IFC file and automatically instantiates IFC entities in accordance with the predefined semantic schema.
* **Phase 2: Attribute Extraction**: The algorithm traverses the complex objectified relationship trees of the IFC schema to extract critical performance parameters of the entities, encapsulating them as attribute values within the nodes.
* **Phase 3: Topological Mapping**: The algorithm transforms and maps the implicit associations within the IFC format into explicit semantic relationships within the Spatial KG, thereby generating structured triples in CSV format.

*(Note: The generated JSON and CSV artifacts from Phase 3 are then seamlessly utilized for direct bulk ingestion into the Neo4j graph database and the generation of interactive HTML visual representations).*

## 2. Regulatory Knowledge Graph Prompts

This file (`prompts_regulatory_kg.md` located in the root directory) contains the comprehensive three-stage prompting strategy designed to drive the large language model in extracting, evaluating, and refining knowledge triples from unstructured regulatory texts. 

The prompting pipeline is architected into three specific stages:
* **Stage 1: Initial Extraction**: Parses triples by enforcing predefined ontology categories, segmenting texts into clause-based units, recognizing cited documents, and translating embedded images.
* **Stage 2: Iterative Feedback**: Autonomously evaluates initial outputs against the source text to rectify potential extraction omissions and repair malformed data structures.
* **Stage 3: Final Canonicalization**: Performs logical consistency checks, eliminates invalid categories, cleans redundant characters, and deduplicates identical triples to improve overall data accuracy.

## 3. BIM Navigator Graph Retrieval Tools

This module details the implementation logic of the retrieval tools and their application within the multi-agent system. These functions, consolidated into a single script (`spatial_graph_retrieval_tools.py`) located in the root directory, are triggered by the large language model via Azure OpenAI Function Calling to execute Neo4j queries in a local Python environment.

### Core Functions
* `get_ifc_entity_properties`: Executes exact-match Cypher queries on IfcType and uses Python JSON parsing to traverse deeply nested Pset/Qto stringified dictionaries for precise attribute extraction.
* `get_elements_in_space`: Performs multi-hop relational traversing in Neo4j (e.g., matching across Bounds, Contains, or Serves edges) starting from a specific Space node.
* `count_ifc_entities`: Combines Neo4j structural retrieval with Python-level dynamic iteration to filter and aggregate nodes matching specific physical constraints.
* `get_connected_elements`: Utilizes dynamic path matching in Cypher to identify surrounding topological components based on parameterized relationship types.
* `calculate_spatial_distance`: Invokes Neo4j’s built-in `shortestPath()` graph algorithm to compute the minimum topological hop-count between components, providing a reliable basis for spatial rationality analysis.

### Technical Architecture and Security Properties
* **Driver Support**: Uses the official `neo4j` Python driver.
* **Connection Mode**: Employs a retrieval class encapsulation supporting database connection pool reuse to optimize concurrent retrieval performance.
* **Data Security**: All Cypher statements utilize parameterization for entity properties. For structural variables that Neo4j does not natively support for parameterization, the system implements a strict whitelist validation mechanism in the Python execution layer prior to any f-string interpolation. Specifically, the `relation_type` parameter in the `get_connected_elements` function is strictly validated against an allowed list of semantic relationships. This dual approach effectively defends against injection risks.

## 4. Multi-Agent System Prompts

This file (`prompts_mas_agents.md` located in the root directory) contains the detailed system prompts governing the specific behaviors and cognitive architectures of the four collaborative agents. 

To strictly align with the dual-track cognitive architecture detailed in the manuscript, the prompt scripts define the following specific reasoning workflows:
* **Task Planner**: Executes a Decomposed CoT workflow for intent parsing and global task routing.
* **BIM Navigator**: Utilizes a ReAct Engine loop to autonomously invoke graph retrieval tools and extract verified spatial evidence.
* **Regulation Expert**: Employs a ReAct Engine loop to perform semantic vector searches and retrieve gold-standard compliance evidence.
* **Decision Maker**: Executes a Synthesis CoT workflow to cross-compare multi-source payloads and generate deterministic decision reports.


## Usage Instructions

Install the required Python packages:
```bash
pip install ifcopenshell pandas networkx pyvis neo4j