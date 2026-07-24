import json
from neo4j import GraphDatabase

class GraphRetrievalTools:
    """
    Backend retrieval utility class for the BIM Navigator agent.
    This class encapsulates Cypher-based Neo4j graph database query logic,
    designed to support the Large Language Model (LLM) in extracting spatial 
    information via the Azure OpenAI Function Calling mechanism.
    """
    
    def __init__(self, uri, user, password):
        """
        Initializes the Neo4j database driver with connection credentials.
        """
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        """
        Closes the database connection pool.
        """
        self.driver.close()

    def get_ifc_entity_properties(self, entity_type, property_name):
        """
        Function 1: Get_ifc_entity_properties
        Executes exact-match Cypher queries on IfcType and uses Python json parsing 
        to traverse deeply nested Pset/Qto stringified dictionaries.
        """
        query = """
        MATCH (n) WHERE n.ifc_type = $entity_type 
        RETURN n.id AS id, n.raw_properties AS props
        """
        
        def _execute(tx):
            results = tx.run(query, entity_type=entity_type)
            extracted_data = []
            for record in results:
                try:
                    props_dict = json.loads(record['props'])
                    # Deep traverse target properties within Pset or Qto
                    for pset, properties in props_dict.items():
                        if property_name in properties:
                            extracted_data.append({
                                'GlobalId': record['id'], 
                                'Value': properties[property_name]
                            })
                except (json.JSONDecodeError, TypeError):
                    continue
            return extracted_data
            
        with self.driver.session() as session:
            return session.execute_read(_execute)

    def get_elements_in_space(self, space_name, element_category):
        """
        Function 2: Get_elements_in_space
        Performs multi-hop relational traversing in Neo4j (e.g., matching across Bounds, 
        Contains, or Serves edges) starting from a specific Space node.
        """
        query = """
        MATCH (s:Space {label: $space_name})-[r]-(e)
        WHERE e.type = $element_category
        RETURN e.id AS id, e.ifc_type AS ifc_type, type(r) AS relation
        """
        
        def _execute(tx):
            results = tx.run(query, space_name=space_name, element_category=element_category)
            return [record.data() for record in results]
            
        with self.driver.session() as session:
            return session.execute_read(_execute)

    def count_ifc_entities(self, entity_type, condition_key, condition_value):
        """
        Function 3: Count_ifc_entities
        Combines Neo4j structural retrieval with Python-level dynamic iteration to filter 
        and aggregate nodes matching specific physical constraints.
        """
        query = """
        MATCH (n) WHERE n.ifc_type = $entity_type
        RETURN n.raw_properties AS props
        """
        
        def _execute(tx):
            results = tx.run(query, entity_type=entity_type)
            match_count = 0
            for record in results:
                try:
                    props_dict = json.loads(record['props'])
                    # Check if any property set contains the matching key-value pair
                    if any(condition_key in p_set and p_set[condition_key] == condition_value 
                           for p_set in props_dict.values()):
                        match_count += 1
                except (json.JSONDecodeError, TypeError):
                    continue
            return {"Count": match_count, "Condition": f"{condition_key} = {condition_value}"}
            
        with self.driver.session() as session:
            return session.execute_read(_execute)

    def get_connected_elements(self, source_id, relation_type):
        """
        Function 4: Get_connected_elements
        Utilizes dynamic path matching (a)-[r]-(b) in Cypher to identify surrounding 
        topological components based on parameterized relationship types.
        
        Security Implementation: Implements a strict whitelist validation mechanism in the 
        Python execution layer prior to any f-string interpolation to defend against injection risks.
        """
        
        # Strict whitelist validation mechanism for structural variables
        allowed_relations = {"Has", "Bounds", "Connects", "Hosts", "Contains", "Serves"}
        if relation_type not in allowed_relations:
            return {"Error": "Invalid or unauthorized relationship type requested."}
        
        # Safe f-string interpolation post-validation
        query = f"""
        MATCH (a {{id: $source_id}})-[r:{relation_type}]-(b)
        RETURN b.id AS target_id, b.type AS target_type, b.ifc_type AS ifc_type
        """
        
        def _execute(tx):
            # Standard Cypher parameterization used for entity properties
            results = tx.run(query, source_id=source_id)
            return [record.data() for record in results]
            
        with self.driver.session() as session:
            return session.execute_read(_execute)

    def calculate_spatial_distance(self, entity_id_A, entity_id_B):
        """
        Function 5: Calculate_spatial_distance
        Invokes Neo4j's built-in shortestPath() graph algorithm to compute the minimum 
        topological hop-count between two target entities.
        """
        query = """
        MATCH p=shortestPath((a {id: $idA})-[*]-(b {id: $idB}))
        RETURN length(p) AS distance, [n IN nodes(p) | n.id] AS path
        """
        
        def _execute(tx):
            result = tx.run(query, idA=entity_id_A, idB=entity_id_B).single()
            if result:
                return {"Topological_Distance": result['distance'], "Path": result['path']}
            return {"Error": "No physical connection path found."}
            
        with self.driver.session() as session:
            return session.execute_read(_execute)

# Example Usage
if __name__ == "__main__":
    # Initialize the retrieval tools (Replace with actual Neo4j credentials)
    # tools = GraphRetrievalTools("bolt://localhost:7687", "neo4j", "password")
    
    # Example Function Call
    # connected = tools.get_connected_elements("2O2Fr$t4X7Zf8NOew3FL9r", "Bounds")
    # print(connected)
    
    # tools.close()
    pass