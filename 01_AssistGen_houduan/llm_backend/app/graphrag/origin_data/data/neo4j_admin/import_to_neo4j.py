"""
Neo4j 鏁版嵁鎵归噺瀵煎叆鑴氭湰
浣跨敤鏂瑰紡: python import_to_neo4j.py
"""
import csv
import os
import sys
from pathlib import Path

# 璇峰厛瀹夎 neo4j 椹卞姩: pip install neo4j
try:
    from neo4j import GraphDatabase
except ImportError:
    print("璇峰厛瀹夎 neo4j 椹卞姩: pip install neo4j")
    sys.exit(1)

# ============ 閰嶇疆鍖?============
# 璇锋牴鎹疄闄呮儏鍐典慨鏀逛互涓嬮厤缃?NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")  # 鏀规垚浣犵殑瀵嗙爜

# CSV 鏂囦欢鎵€鍦ㄧ洰褰?CSV_DIR = Path(__file__).parent
# ==============================

class Neo4jImporter:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def _normalize_headers(self, headers):
        """瑙勮寖鍖朇SV琛ㄥご锛屽鐞?Neo4j 鐗规畩鏍煎紡锛?        - ':START_ID(Product)' -> 'START_ID' (杈规枃浠秇eader浠ュ啋鍙峰紑澶?
        - 'productId:ID(Product)' -> 'productId' (鑺傜偣鏂囦欢header)
        - 'ProductName' -> 'ProductName' (鏃犲啋鍙风殑鏅€歨eader)
        """
        result = {}
        for old_key in headers:
            if old_key.startswith(':'):
                # 杈规枃浠舵牸寮?':START_ID(Product)' -> 鍙栧啋鍙峰悗绗竴娈?                new_key = old_key.split(':')[1].split('(')[0].strip()
            elif ':' in old_key:
                # 鑺傜偣鏂囦欢鏍煎紡 'productId:ID(Product)' -> 鍙栧啋鍙峰墠绗竴娈?                new_key = old_key.split(':')[0]
            else:
                # 鏅€氭牸寮忕洿鎺ヤ娇鐢?                new_key = old_key
            result[old_key] = new_key
        return result

    def _read_csv(self, file_path):
        """璇诲彇CSV骞惰鑼冨寲琛ㄥご"""
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            # 瑙勮寖鍖栬〃澶存槧灏?            original_headers = reader.fieldnames
            header_map = self._normalize_headers(original_headers)

            rows = []
            for row in reader:
                new_row = {}
                for old_key, new_key in header_map.items():
                    new_row[new_key] = row.get(old_key, '')
                rows.append(new_row)
            return rows

    def close(self):
        self.driver.close()

    def run_query(self, query, params=None):
        with self.driver.session() as session:
            result = session.run(query, params)
            return result.consume()

    def clear_database(self):
        """娓呯┖鏁版嵁搴?""
        print("姝ｅ湪娓呯┖鏁版嵁搴?..")
        self.run_query("MATCH (n) DETACH DELETE n")
        print("鏁版嵁搴撳凡娓呯┖")

    # ============ 鑺傜偣瀵煎叆 ============

    def import_product_nodes(self):
        print("瀵煎叆 Product 鑺傜偣...")
        file_path = CSV_DIR / "product_nodes.csv"
        query = """
        CREATE (:Product {
          productId: $productId,
          ProductName: $ProductName,
          SupplierID: $SupplierID,
          CategoryID: $CategoryID,
          QuantityPerUnit: $QuantityPerUnit,
          UnitPrice: toFloat($UnitPrice),
          UnitsInStock: toInteger($UnitsInStock),
          UnitsOnOrder: toInteger($UnitsOnOrder),
          ReorderLevel: toInteger($ReorderLevel),
          Discontinued: $Discontinued,
          CategoryName: $CategoryName,
          SupplierName: $SupplierName
        })
        """
        count = 0
        rows = self._read_csv(file_path)
        with self.driver.session() as session:
            for row in rows:
                session.run(query, row)
                count += 1
        print(f"  宸插鍏?{count} 涓?Product 鑺傜偣")

    def import_category_nodes(self):
        print("瀵煎叆 Category 鑺傜偣...")
        file_path = CSV_DIR / "category_nodes.csv"
        query = """
        CREATE (:Category {
          categoryId: $categoryId,
          CategoryName: $CategoryName,
          Description: $Description,
          Picture: $Picture
        })
        """
        count = 0
        rows = self._read_csv(file_path)
        with self.driver.session() as session:
            for row in rows:
                session.run(query, row)
                count += 1
        print(f"  宸插鍏?{count} 涓?Category 鑺傜偣")

    def import_supplier_nodes(self):
        print("瀵煎叆 Supplier 鑺傜偣...")
        file_path = CSV_DIR / "supplier_nodes.csv"
        query = """
        CREATE (:Supplier {
          supplierId: $supplierId,
          CompanyName: $CompanyName,
          ContactName: $ContactName,
          ContactTitle: $ContactTitle,
          Address: $Address,
          City: $City,
          Region: $Region,
          PostalCode: $PostalCode,
          Country: $Country,
          Phone: $Phone,
          Fax: $Fax,
          HomePage: $HomePage
        })
        """
        count = 0
        rows = self._read_csv(file_path)
        with self.driver.session() as session:
            for row in rows:
                session.run(query, row)
                count += 1
        print(f"  宸插鍏?{count} 涓?Supplier 鑺傜偣")

    def import_customer_nodes(self):
        print("瀵煎叆 Customer 鑺傜偣...")
        file_path = CSV_DIR / "customer_nodes.csv"
        query = """
        CREATE (:Customer {
          customerId: $customerId,
          CompanyName: $CompanyName,
          ContactName: $ContactName,
          ContactTitle: $ContactTitle,
          Address: $Address,
          City: $City,
          Region: $Region,
          PostalCode: $PostalCode,
          Country: $Country,
          Phone: $Phone,
          Fax: $Fax
        })
        """
        count = 0
        rows = self._read_csv(file_path)
        with self.driver.session() as session:
            for row in rows:
                session.run(query, row)
                count += 1
        print(f"  宸插鍏?{count} 涓?Customer 鑺傜偣")

    def import_employee_nodes(self):
        print("瀵煎叆 Employee 鑺傜偣...")
        file_path = CSV_DIR / "employee_nodes.csv"
        query = """
        CREATE (:Employee {
          employeeId: $employeeId,
          LastName: $LastName,
          FirstName: $FirstName,
          Title: $Title,
          TitleOfCourtesy: $TitleOfCourtesy,
          BirthDate: $BirthDate,
          HireDate: $HireDate,
          Address: $Address,
          City: $City,
          Region: $Region,
          PostalCode: $PostalCode,
          Country: $Country,
          HomePhone: $HomePhone,
          Extension: $Extension,
          Photo: $Photo,
          Notes: $Notes,
          ReportsTo: $ReportsTo
        })
        """
        count = 0
        rows = self._read_csv(file_path)
        with self.driver.session() as session:
            for row in rows:
                session.run(query, row)
                count += 1
        print(f"  宸插鍏?{count} 涓?Employee 鑺傜偣")

    def import_shipper_nodes(self):
        print("瀵煎叆 Shipper 鑺傜偣...")
        file_path = CSV_DIR / "shipper_nodes.csv"
        query = """
        CREATE (:Shipper {
          shipperId: $shipperId,
          CompanyName: $CompanyName,
          Phone: $Phone
        })
        """
        count = 0
        rows = self._read_csv(file_path)
        with self.driver.session() as session:
            for row in rows:
                session.run(query, row)
                count += 1
        print(f"  宸插鍏?{count} 涓?Shipper 鑺傜偣")

    def import_order_nodes(self):
        print("瀵煎叆 Order 鑺傜偣...")
        file_path = CSV_DIR / "order_nodes.csv"
        query = """
        CREATE (:Order {
          orderId: $orderId,
          OrderDate: $OrderDate,
          RequiredDate: $RequiredDate,
          ShippedDate: $ShippedDate,
          Freight: toFloat($Freight),
          ShipName: $ShipName,
          ShipAddress: $ShipAddress,
          ShipCity: $ShipCity,
          ShipRegion: $ShipRegion,
          ShipPostalCode: $ShipPostalCode,
          ShipCountry: $ShipCountry,
          CustomerName: $CustomerName,
          LastName: $LastName,
          FirstName: $FirstName,
          ShipperName: $ShipperName
        })
        """
        count = 0
        rows = self._read_csv(file_path)
        with self.driver.session() as session:
            for row in rows:
                session.run(query, row)
                count += 1
        print(f"  宸插鍏?{count} 涓?Order 鑺傜偣")

    def import_review_nodes(self):
        print("瀵煎叆 Review 鑺傜偣...")
        file_path = CSV_DIR / "review_nodes.csv"
        query = """
        CREATE (:Review {
          reviewId: $reviewId,
          ProductName: $ProductName,
          CustomerName: $CustomerName,
          Rating: toFloat($Rating),
          ReviewText: $ReviewText,
          ReviewDate: $ReviewDate,
          CategoryName: $CategoryName
        })
        """
        count = 0
        rows = self._read_csv(file_path)
        with self.driver.session() as session:
            for row in rows:
                session.run(query, row)
                count += 1
        print(f"  宸插鍏?{count} 涓?Review 鑺傜偣")

    # ============ 鍏崇郴瀵煎叆 ============

    def import_relationships(self):
        """瀵煎叆鎵€鏈夊叧绯?""
        print("\n寮€濮嬪鍏ュ叧绯?..")

        self.import_product_category()
        self.import_product_supplier()
        self.import_customer_order()
        self.import_employee_order()
        self.import_order_shipper()
        self.import_order_product()
        self.import_employee_reports_to()
        self.import_customer_review()
        self.import_review_product()

    def import_product_category(self):
        """Product -> Category (BELONGS_TO)"""
        print("  瀵煎叆 BELONGS_TO 鍏崇郴...")
        file_path = CSV_DIR / "product_category_edges.csv"
        query = """
        MATCH (p:Product {productId: $start_id})
        MATCH (c:Category {categoryId: $end_id})
        CREATE (p)-[:BELONGS_TO]->(c)
        """
        count = 0
        rows = self._read_csv(file_path)
        with self.driver.session() as session:
            for row in rows:
                session.run(query, {"start_id": row.get('START_ID', ''), "end_id": row.get('END_ID', '')})
                count += 1
        print(f"    宸插鍏?{count} 鏉?BELONGS_TO 鍏崇郴")

    def import_product_supplier(self):
        """Product -> Supplier (SUPPLIED_BY)"""
        print("  瀵煎叆 SUPPLIED_BY 鍏崇郴...")
        file_path = CSV_DIR / "product_supplier_edges.csv"
        query = """
        MATCH (p:Product {productId: $start_id})
        MATCH (s:Supplier {supplierId: $end_id})
        CREATE (p)-[:SUPPLIED_BY]->(s)
        """
        count = 0
        rows = self._read_csv(file_path)
        with self.driver.session() as session:
            for row in rows:
                session.run(query, {"start_id": row.get('START_ID', ''), "end_id": row.get('END_ID', '')})
                count += 1
        print(f"    宸插鍏?{count} 鏉?SUPPLIED_BY 鍏崇郴")

    def import_customer_order(self):
        """Customer -> Order (PLACED)"""
        print("  瀵煎叆 PLACED 鍏崇郴...")
        file_path = CSV_DIR / "customer_order_edges.csv"
        query = """
        MATCH (c:Customer {customerId: $start_id})
        MATCH (o:Order {orderId: $end_id})
        CREATE (c)-[:PLACED]->(o)
        """
        count = 0
        rows = self._read_csv(file_path)
        with self.driver.session() as session:
            for row in rows:
                session.run(query, {"start_id": row.get('START_ID', ''), "end_id": row.get('END_ID', '')})
                count += 1
        print(f"    宸插鍏?{count} 鏉?PLACED 鍏崇郴")

    def import_employee_order(self):
        """Employee -> Order (PROCESSED)"""
        print("  瀵煎叆 PROCESSED 鍏崇郴...")
        file_path = CSV_DIR / "employee_order_edges.csv"
        query = """
        MATCH (e:Employee {employeeId: $start_id})
        MATCH (o:Order {orderId: $end_id})
        CREATE (e)-[:PROCESSED]->(o)
        """
        count = 0
        rows = self._read_csv(file_path)
        with self.driver.session() as session:
            for row in rows:
                session.run(query, {"start_id": row.get('START_ID', ''), "end_id": row.get('END_ID', '')})
                count += 1
        print(f"    宸插鍏?{count} 鏉?PROCESSED 鍏崇郴")

    def import_order_shipper(self):
        """Order -> Shipper (SHIPPED_VIA)"""
        print("  瀵煎叆 SHIPPED_VIA 鍏崇郴...")
        file_path = CSV_DIR / "order_shipper_edges.csv"
        query = """
        MATCH (o:Order {orderId: $start_id})
        MATCH (s:Shipper {shipperId: $end_id})
        CREATE (o)-[:SHIPPED_VIA]->(s)
        """
        count = 0
        rows = self._read_csv(file_path)
        with self.driver.session() as session:
            for row in rows:
                session.run(query, {"start_id": row.get('START_ID', ''), "end_id": row.get('END_ID', '')})
                count += 1
        print(f"    宸插鍏?{count} 鏉?SHIPPED_VIA 鍏崇郴")

    def import_order_product(self):
        """Order -> Product (CONTAINS)"""
        print("  瀵煎叆 CONTAINS 鍏崇郴...")
        file_path = CSV_DIR / "order_product_edges.csv"
        query = """
        MATCH (o:Order {orderId: $start_id})
        MATCH (p:Product {productId: $end_id})
        CREATE (o)-[:CONTAINS {
          UnitPrice: toFloat($UnitPrice),
          Quantity: toInteger($Quantity),
          Discount: toFloat($Discount)
        }]->(p)
        """
        count = 0
        rows = self._read_csv(file_path)
        with self.driver.session() as session:
            for row in rows:
                params = {
                    "start_id": row.get('START_ID', ''),
                    "end_id": row.get('END_ID', ''),
                    "UnitPrice": row.get('UnitPrice', '0'),
                    "Quantity": row.get('Quantity', '0'),
                    "Discount": row.get('Discount', '0')
                }
                session.run(query, params)
                count += 1
        print(f"    宸插鍏?{count} 鏉?CONTAINS 鍏崇郴")

    def import_employee_reports_to(self):
        """Employee -> Employee (REPORTS_TO)"""
        print("  瀵煎叆 REPORTS_TO 鍏崇郴...")
        file_path = CSV_DIR / "employee_reports_to_edges.csv"
        query = """
        MATCH (e:Employee {employeeId: $start_id})
        MATCH (m:Employee {employeeId: $end_id})
        CREATE (e)-[:REPORTS_TO]->(m)
        """
        count = 0
        rows = self._read_csv(file_path)
        with self.driver.session() as session:
            for row in rows:
                session.run(query, {"start_id": row.get('START_ID', ''), "end_id": row.get('END_ID', '')})
                count += 1
        print(f"    宸插鍏?{count} 鏉?REPORTS_TO 鍏崇郴")

    def import_customer_review(self):
        """Customer -> Review (WROTE)"""
        print("  瀵煎叆 WROTE 鍏崇郴...")
        file_path = CSV_DIR / "customer_review_edges.csv"
        query = """
        MATCH (c:Customer {customerId: $start_id})
        MATCH (r:Review {reviewId: $end_id})
        CREATE (c)-[:WROTE]->(r)
        """
        count = 0
        rows = self._read_csv(file_path)
        with self.driver.session() as session:
            for row in rows:
                session.run(query, {"start_id": row.get('START_ID', ''), "end_id": row.get('END_ID', '')})
                count += 1
        print(f"    宸插鍏?{count} 鏉?WROTE 鍏崇郴")

    def import_review_product(self):
        """Review -> Product (ABOUT)"""
        print("  瀵煎叆 ABOUT 鍏崇郴...")
        file_path = CSV_DIR / "review_product_edges.csv"
        query = """
        MATCH (r:Review {reviewId: $start_id})
        MATCH (p:Product {productId: $end_id})
        CREATE (r)-[:ABOUT]->(p)
        """
        count = 0
        rows = self._read_csv(file_path)
        with self.driver.session() as session:
            for row in rows:
                session.run(query, {"start_id": row.get('START_ID', ''), "end_id": row.get('END_ID', '')})
                count += 1
        print(f"    宸插鍏?{count} 鏉?ABOUT 鍏崇郴")

    def import_all(self):
        """鎵ц鍏ㄩ噺瀵煎叆"""
        print("=" * 50)
        print("寮€濮嬪鍏?Neo4j 鏁版嵁")
        print("=" * 50)

        # 娓呯┖鏁版嵁搴?        self.clear_database()

        # 瀵煎叆鑺傜偣
        print("\n--- 瀵煎叆鑺傜偣 ---")
        self.import_product_nodes()
        self.import_category_nodes()
        self.import_supplier_nodes()
        self.import_customer_nodes()
        self.import_employee_nodes()
        self.import_shipper_nodes()
        self.import_order_nodes()
        self.import_review_nodes()

        # 瀵煎叆鍏崇郴
        self.import_relationships()

        print("\n" + "=" * 50)
        print("鏁版嵁瀵煎叆瀹屾垚!")
        print("=" * 50)

        # 楠岃瘉
        print("\n楠岃瘉鏁版嵁:")
        with self.driver.session() as session:
            result = session.run("MATCH (n) RETURN labels(n)[0] as label, count(*) as count ORDER BY label")
            for record in result:
                print(f"  {record['label']}: {record['count']} 涓妭鐐?)

            rel_result = session.run("MATCH ()-[r]->() RETURN type(r) as rel_type, count(*) as count ORDER BY rel_type")
            for record in rel_result:
                print(f"  {record['rel_type']}: {record['count']} 鏉″叧绯?)


def main():
    # 鍏堟鏌?neo4j 椹卞姩
    try:
        from neo4j import GraphDatabase
    except ImportError:
        print("姝ｅ湪瀹夎 neo4j 椹卞姩...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "neo4j"])
        from neo4j import GraphDatabase

    importer = Neo4jImporter(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)

    try:
        importer.import_all()
    finally:
        importer.close()


if __name__ == "__main__":
    main()
