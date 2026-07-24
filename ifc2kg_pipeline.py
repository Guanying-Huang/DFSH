import ifcopenshell
import pandas as pd
import json
import networkx as nx
from pyvis.network import Network

# Define the mapping from IFC classes to Semantic Schema categories
SEMANTIC_MAPPING = {
    # Project (Global Node)
    'IfcProject': 'Project',
    # Boundary
    'IfcWall': 'Boundary',
    'IfcColumn': 'Boundary',
    'IfcCovering': 'Boundary',
    'IfcSlab': 'Boundary',
    # Connection
    'IfcWindow': 'Connection',
    'IfcDoor': 'Connection',
    # Space
    'IfcSpace': 'Space',
    # MEP Component
    'IfcAirTerminal': 'MEP_Component',
    'IfcLightFixture': 'MEP_Component',
    'IfcSanitaryTerminal': 'MEP_Component',
    # Equipment
    'IfcBuildingElementProxy': 'Equipment'
}

class IFC2KGPipeline:
    def __init__(self, ifc_path):
        """Initialize the pipeline to process an IFC file into a Spatial KG."""
        self.ifc_path = ifc_path
        self.ifc_file = None
        
        # Data artifacts generated across the three phases
        self.parsed_entities = [] # Stores initialized objects (Phase 1)
        self.nodes_data = []      # Stores nodes with extracted attributes (Phase 2)
        self.triples = []         # Stores semantic edges (Phase 3)
        self.graph = nx.DiGraph() # Final NetworkX graph

    # =========================================================
    # Phase 1: Initialization and Parsing
    # =========================================================
    def phase_1_initialization_and_parsing(self):
        """Parses the IFC topology and instantiates entities based on semantic schema."""
        print("--- Phase 1: Initialization and Parsing ---")
        self.ifc_file = ifcopenshell.open(self.ifc_path)

        for ifc_class, semantic_type in SEMANTIC_MAPPING.items():
            elements = self.ifc_file.by_type(ifc_class)
            for el in elements:
                self.parsed_entities.append({
                    'element': el,
                    'ifc_class': ifc_class,
                    'semantic_type': semantic_type
                })
        print(f"Instantiated {len(self.parsed_entities)} entities in accordance with the predefined semantic schema.")

    # =========================================================
    # Phase 2: Attribute Extraction
    # =========================================================
    def phase_2_attribute_extraction(self):
        """Traverses objectified relationships to extract performance parameters."""
        print("--- Phase 2: Attribute Extraction ---")
        for item in self.parsed_entities:
            el = item['element']
            props = self._get_properties_and_quantities(el)

            node_data = {
                'GlobalId': el.GlobalId,
                'Name': el.Name if el.Name else "Unnamed",
                'IfcType': item['ifc_class'],
                'SemanticType': item['semantic_type'],
                'Properties': props
            }
            self.nodes_data.append(node_data)

        # Inject "Outdoor" boundary anchor node for holistic reasoning
        self.nodes_data.append({
            'GlobalId': 'OUTDOOR_ANCHOR',
            'Name': 'Outdoor Environment',
            'IfcType': 'VirtualNode',
            'SemanticType': 'Space',
            'Properties': {'Description': 'Virtual boundary anchor for external connectivity reasoning'}
        })
        
        # Save output
        with open("extracted_nodes.json", 'w', encoding='utf-8') as f:
            json.dump(self.nodes_data, f, indent=4, ensure_ascii=False)
            
        print(f"Extracted performance parameters for {len(self.nodes_data)} nodes (encapsulated and saved to extracted_nodes.json).")

    # =========================================================
    # Phase 3: Topological Mapping
    # =========================================================
    def phase_3_topological_mapping(self):
        """Transforms implicit IFC associations into explicit semantic relationships."""
        print("--- Phase 3: Topological Mapping ---")
        
        # 1. Project -> Has -> Space
        projects = self.ifc_file.by_type('IfcProject')
        spaces = self.ifc_file.by_type('IfcSpace')
        if projects:
            project_id = projects[0].GlobalId
            for space in spaces:
                self.triples.append((project_id, 'Has', space.GlobalId))
            self.triples.append((project_id, 'Has', 'OUTDOOR_ANCHOR'))

        # 2. Bounds & Connects
        for rel in self.ifc_file.by_type('IfcRelSpaceBoundary'):
            space = rel.RelatingSpace
            element = rel.RelatedBuildingElement
            if space and element:
                sem_type = SEMANTIC_MAPPING.get(element.is_a())
                if sem_type == 'Boundary':
                    self.triples.append((element.GlobalId, 'Bounds', space.GlobalId))
                elif sem_type == 'Connection':
                    self.triples.append((element.GlobalId, 'Connects', space.GlobalId))

        # 3. Connectivity to Outdoor Environment
        for node in self.nodes_data:
            if self._is_element_external(node['Properties']):
                if node['SemanticType'] == 'Boundary':
                    self.triples.append((node['GlobalId'], 'Bounds', 'OUTDOOR_ANCHOR'))
                elif node['SemanticType'] == 'Connection':
                    self.triples.append((node['GlobalId'], 'Connects', 'OUTDOOR_ANCHOR'))

        # 4. Hosts
        for voids_rel in self.ifc_file.by_type('IfcRelVoidsElement'):
            host_element = voids_rel.RelatingBuildingElement
            opening = voids_rel.RelatedOpeningElement
            if opening and host_element and SEMANTIC_MAPPING.get(host_element.is_a()) == 'Boundary':
                if hasattr(opening, 'HasFillings'):
                    for fills_rel in opening.HasFillings:
                        filling_element = fills_rel.RelatedBuildingElement
                        if filling_element and SEMANTIC_MAPPING.get(filling_element.is_a()) == 'Connection':
                            self.triples.append((host_element.GlobalId, 'Hosts', filling_element.GlobalId))

        # 5. Contains & Serves
        for rel in self.ifc_file.by_type('IfcRelContainedInSpatialStructure'):
            space = rel.RelatingStructure
            if space and space.is_a('IfcSpace'):
                for element in rel.RelatedElements:
                    sem_type = SEMANTIC_MAPPING.get(element.is_a())
                    if sem_type == 'Equipment':
                        self.triples.append((space.GlobalId, 'Contains', element.GlobalId))
                    elif sem_type == 'MEP_Component':
                        self.triples.append((element.GlobalId, 'Serves', space.GlobalId))

        # Export Triples in CSV format
        triples_df = pd.DataFrame(self.triples, columns=['Head', 'Relation', 'Tail'])
        triples_df.drop_duplicates(inplace=True)
        triples_df.to_csv("semantic_triples.csv", index=False)
        print(f"Generated {len(triples_df)} explicit semantic triples (saved to semantic_triples.csv).")

    # =========================================================
    # Post-Processing: Graph Construction and Visualization
    # =========================================================
    def build_networkx_graph_and_export(self, json_out_path):
        """Constructs NetworkX graph for local structural validation and JSON export."""
        print("--- Post-Processing: Building NetworkX Graph ---")
        
        for node in self.nodes_data:
            node_id = node['GlobalId']
            flat_props = {
                'name': node['Name'],
                'ifc_type': node['IfcType'],
                'semantic_type': node['SemanticType'],
                'raw_properties': json.dumps(node['Properties'], ensure_ascii=False)
            }
            self.graph.add_node(node_id, **flat_props)

        for head, rel, tail in self.triples:
            if self.graph.has_node(head) and self.graph.has_node(tail):
                self.graph.add_edge(head, tail, type=rel)

        # Export for visualization
        graph_data = {'nodes': [], 'edges': []}
        for node_id, data in self.graph.nodes(data=True):
            graph_data['nodes'].append({
                'id': node_id,
                'type': data.get('semantic_type', 'Unknown'),
                'label': data.get('name', node_id),
                'properties': {
                    'ifc_type': data.get('ifc_type'),
                    'raw_properties': data.get('raw_properties')
                }
            })
            
        for head, tail, data in self.graph.edges(data=True):
            graph_data['edges'].append({
                'source': head,
                'target': tail,
                'type': data.get('type', 'related_to')
            })

        with open(json_out_path, 'w', encoding='utf-8') as f:
            json.dump(graph_data, f, indent=4, ensure_ascii=False)
        print(f"Exported JSON Graph artifact to {json_out_path}.")

    def generate_html_visualization(self, json_in_path, html_out_path):
        """Generates a high-fidelity interactive HTML visualization."""
        print("--- Post-Processing: Generating HTML Visualization ---")
        with open(json_in_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        net = Network(height="850px", width="100%", bgcolor="#ffffff", font_color="black", directed=True)

        COLOR_MAP = {
            "Project": "#000000",
            "Space": "#F8766D",
            "Boundary": "#C77CFF",
            "Connection": "#619CFF",
            "Equipment": "#00BA38",
            "MEP_Component": "#F5B041"
        }

        SIZE_MAP = {
            "Project": 40, "Space": 30, "Boundary": 15,
            "Connection": 15, "Equipment": 15, "MEP_Component": 15
        }

        for node in data['nodes']:
            node_id = node['id']
            semantic_type = node['type']
            ifc_type = node['properties'].get('ifc_type', '')
            
            color = COLOR_MAP.get(semantic_type, "#CCCCCC")
            size = SIZE_MAP.get(semantic_type, 15)
            
            hover_text = f"<b>Semantic Type:</b> {semantic_type}<br><b>IFC Entity:</b> {ifc_type}<br><b>GlobalId:</b> {node_id}"
            
            net.add_node(
                node_id,
                label=semantic_type if semantic_type in ["Project", "Space"] else "", 
                color=color,
                title=hover_text,
                shape="dot",
                size=size
            )

        for edge in data['edges']:
            net.add_edge(
                edge['source'], 
                edge['target'], 
                title=edge['type'], 
                color="#A0A0A0",
                arrows="to",
                width=1.5 if edge['type'] == 'Has' else 1.0 
            )

        net.set_options("""
        {
          "physics": {
            "forceAtlas2Based": {
              "gravitationalConstant": -150,
              "centralGravity": 0.01,
              "springLength": 100,
              "springConstant": 0.08,
              "damping": 0.4,
              "avoidOverlap": 0
            },
            "maxVelocity": 50,
            "minVelocity": 0.1,
            "solver": "forceAtlas2Based",
            "timestep": 0.5
          }
        }
        """)

        net.show(html_out_path, notebook=False)
        print(f"Visualization successfully saved to {html_out_path}")

    # =========================================================
    # Internal Helper Methods
    # =========================================================
    def _get_properties_and_quantities(self, element):
        """Extracts properties (Pset) and quantities (Qto) from an IFC element."""
        props = {}
        if hasattr(element, "IsDefinedBy"):
            for definition in element.IsDefinedBy:
                if definition.is_a('IfcRelDefinesByProperties'):
                    property_set = definition.RelatingPropertyDefinition
                    
                    if property_set.is_a('IfcPropertySet'):
                        pset_name = property_set.Name
                        props[pset_name] = {}
                        for prop in property_set.HasProperties:
                            if prop.is_a('IfcPropertySingleValue') and prop.NominalValue:
                                props[pset_name][prop.Name] = prop.NominalValue.wrappedValue
                                
                    elif property_set.is_a('IfcElementQuantity'):
                        qto_name = property_set.Name
                        props[qto_name] = {}
                        for quantity in property_set.Quantities:
                            for attr in ['LengthValue', 'AreaValue', 'VolumeValue', 'WeightValue']:
                                if hasattr(quantity, attr):
                                    props[qto_name][quantity.Name] = getattr(quantity, attr)
                                    break
        return props

    def _is_element_external(self, properties):
        """Checks if the element is flagged as external."""
        for pset_name, props_dict in properties.items():
            if 'IsExternal' in props_dict:
                val = props_dict['IsExternal']
                if val in [True, 1, 'True', '1', 'T']:
                    return True
        return False

    # =========================================================
    # Main Execution Trigger
    # =========================================================
    def execute(self):
        """Runs the complete IFC2KG pipeline."""
        print(f"Loading IFC file: {self.ifc_path}\n")
        
        self.phase_1_initialization_and_parsing()
        self.phase_2_attribute_extraction()
        self.phase_3_topological_mapping()
        
        print("\nInitiating Graph Export and Visualization...")
        self.build_networkx_graph_and_export("spatial_kg_final.json")
        self.generate_html_visualization("spatial_kg_final.json", "spatial_kg_visualization.html")
        
        print("\n✅ IFC2KG Pipeline Execution Complete.")


if __name__ == "__main__":
    # Ensure you replace "sample_building.ifc" with your actual IFC file path
    pipeline = IFC2KGPipeline("sample_building.ifc")
    pipeline.execute()