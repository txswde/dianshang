"""
浠?CSV 鏂囦欢鍒涘缓 Neo4j 鍏崇郴杈?"""
import csv
import os
from neo4j import GraphDatabase

# Neo4j 杩炴帴閰嶇疆
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")  # 浠?.env 鏂囦欢涓殑瀵嗙爜

# CSV 鏂囦欢璺緞
BASE_DIR = r"D:\BaiduNetdiskDownload\agent\Agent\5_AssistGen\AssistGen\01_AssistGen_houduan\llm_backend\app\graphrag\origin_data\data\neo4j_admin"
PRODUCT_CATEGORY_CSV = f"{BASE_DIR}\\product_category_edges.csv"
PRODUCT_SUPPLIER_CSV = f"{BASE_DIR}\\product_supplier_edges.csv"


def create_belongs_to_relationships(driver):
    """鍒涘缓 BELONGS_TO 鍏崇郴"""
    print("姝ｅ湪鍒涘缓 BELONGS_TO 鍏崇郴...")

    with driver.session() as session:
        # 鍏堟煡鐪?CSV 鍐呭
        with open(PRODUCT_CATEGORY_CSV, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        print(f"璇诲彇鍒?{len(rows)} 鏉?BELONGS_TO 璁板綍")

        count = 0
        for row in rows:
            product_id = row.get(':START_ID(Product)') or row.get('productId')
            category_id = row.get(':END_ID(Category)') or row.get('categoryId')

            if not product_id or not category_id:
                print(f"璺宠繃鏃犳晥琛? {row}")
                continue

            try:
                result = session.run("""
                    MATCH (p:Product {productId: toInteger($product_id)})
                    MATCH (c:Category {categoryId: toInteger($category_id)})
                    MERGE (p)-[:BELONGS_TO]->(c)
                    RETURN p.ProductName AS product, c.CategoryName AS category
                """, product_id=int(product_id), category_id=int(category_id))

                record = result.single()
                if record:
                    count += 1
                    print(f"  鍒涘缓: {record['product']} -> {record['category']}")
            except Exception as e:
                print(f"  閿欒: productId={product_id}, categoryId={category_id}, error={e}")

        print(f"BELONGS_TO 鍏崇郴鍒涘缓瀹屾垚: {count} 鏉?)


def create_supplied_by_relationships(driver):
    """鍒涘缓 SUPPLIED_BY 鍏崇郴"""
    print("\n姝ｅ湪鍒涘缓 SUPPLIED_BY 鍏崇郴...")

    with driver.session() as session:
        # 鍏堟煡鐪?CSV 鍐呭
        with open(PRODUCT_SUPPLIER_CSV, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        print(f"璇诲彇鍒?{len(rows)} 鏉?SUPPLIED_BY 璁板綍")

        count = 0
        for row in rows:
            product_id = row.get(':START_ID(Product)') or row.get('productId')
            supplier_id = row.get(':END_ID(Supplier)') or row.get('supplierId')

            if not product_id or not supplier_id:
                print(f"璺宠繃鏃犳晥琛? {row}")
                continue

            try:
                result = session.run("""
                    MATCH (p:Product {productId: toInteger($product_id)})
                    MATCH (s:Supplier {supplierId: toInteger($supplier_id)})
                    MERGE (p)-[:SUPPLIED_BY]->(s)
                    RETURN p.ProductName AS product, s.CompanyName AS supplier
                """, product_id=int(product_id), supplier_id=int(supplier_id))

                record = result.single()
                if record:
                    count += 1
                    print(f"  鍒涘缓: {record['product']} -> {record['supplier']}")
            except Exception as e:
                print(f"  閿欒: productId={product_id}, supplierId={supplier_id}, error={e}")

        print(f"SUPPLIED_BY 鍏崇郴鍒涘缓瀹屾垚: {count} 鏉?)


def verify_relationships(driver):
    """楠岃瘉鍏崇郴鍒涘缓缁撴灉"""
    print("\n楠岃瘉鍏崇郴...")
    with driver.session() as session:
        # 妫€鏌ュ叧绯荤被鍨?        result = session.run("CALL db.relationshipTypes()")
        rel_types = [record["relationshipType"] for record in result]
        print(f"鍏崇郴绫诲瀷: {rel_types}")

        # 缁熻鍏崇郴鏁伴噺
        result = session.run("""
            MATCH ()-[r]->()
            RETURN type(r) AS relType, count(*) AS count
        """)
        for record in result:
            print(f"  {record['relType']}: {record['count']} 鏉?)

        # 鏍蜂緥鏌ヨ
        result = session.run("""
            MATCH (p:Product)-[:BELONGS_TO]->(c:Category)
            RETURN p.ProductName AS product, c.CategoryName AS category
            LIMIT 5
        """)
        print("\nBELONGS_TO 鍏崇郴绀轰緥:")
        for record in result:
            print(f"  {record['product']} -> {record['category']}")


def main():
    print("=" * 50)
    print("Neo4j 鍏崇郴鍒涘缓鑴氭湰")
    print("=" * 50)
    print(f"杩炴帴: {NEO4J_URI}")
    print(f"鐢ㄦ埛: {NEO4J_USER}")
    print("=" * 50)

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    try:
        # 楠岃瘉杩炴帴
        driver.verify_connectivity()
        print("杩炴帴鎴愬姛锛乗n")

        # 鍒涘缓鍏崇郴
        create_belongs_to_relationships(driver)
        create_supplied_by_relationships(driver)

        # 楠岃瘉缁撴灉
        verify_relationships(driver)

    except Exception as e:
        print(f"閿欒: {e}")

    finally:
        driver.close()
        print("\n鑴氭湰鎵ц瀹屾垚锛?)


if __name__ == "__main__":
    main()
