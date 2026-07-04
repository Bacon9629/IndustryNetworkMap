// Neo4j unique constraints for core node types (Phase 1.2)
// Apply with:
//   docker exec -it industry-network-map-neo4j cypher-shell -u neo4j -p <password> -f /import/cypher/constraints.cypher
// or paste into Neo4j Browser. Import script also applies these automatically.

CREATE CONSTRAINT company_id_unique IF NOT EXISTS
FOR (n:Company) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT product_id_unique IF NOT EXISTS
FOR (n:Product) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT industry_id_unique IF NOT EXISTS
FOR (n:Industry) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT application_id_unique IF NOT EXISTS
FOR (n:Application) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT source_id_unique IF NOT EXISTS
FOR (n:Source) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT evidence_id_unique IF NOT EXISTS
FOR (n:Evidence) REQUIRE n.id IS UNIQUE;
