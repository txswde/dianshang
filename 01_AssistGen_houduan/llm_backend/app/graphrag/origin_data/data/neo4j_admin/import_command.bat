@echo off

REM Neo4j Admin导入命令
REM 适用于Neo4j 2025.02.0及更高版本
REM 生成时间: 2026-04-03 11:30:00

set NEO4J_ADMIN=D:\BaiduNetdiskDownload\agent\Agent\5_AssistGen\AssistGen\01_AssistGen_houduan\llm_backend\app\graphrag\origin_data\data\neo4j_admin

neo4j-admin database import full neo4j --overwrite-destination ^
  --nodes=Product="%NEO4J_ADMIN%\product_nodes.csv" ^
  --nodes=Category="%NEO4J_ADMIN%\category_nodes.csv" ^
  --nodes=Supplier="%NEO4J_ADMIN%\supplier_nodes.csv" ^
  --nodes=Customer="%NEO4J_ADMIN%\customer_nodes.csv" ^
  --nodes=Employee="%NEO4J_ADMIN%\employee_nodes.csv" ^
  --nodes=Shipper="%NEO4J_ADMIN%\shipper_nodes.csv" ^
  --nodes=Order="%NEO4J_ADMIN%\order_nodes.csv" ^
  --nodes=Review="%NEO4J_ADMIN%\review_nodes.csv" ^
  --relationships=BELONGS_TO="%NEO4J_ADMIN%\product_category_edges.csv" ^
  --relationships=SUPPLIED_BY="%NEO4J_ADMIN%\product_supplier_edges.csv" ^
  --relationships=PLACED="%NEO4J_ADMIN%\customer_order_edges.csv" ^
  --relationships=PROCESSED="%NEO4J_ADMIN%\employee_order_edges.csv" ^
  --relationships=SHIPPED_VIA="%NEO4J_ADMIN%\order_shipper_edges.csv" ^
  --relationships=CONTAINS="%NEO4J_ADMIN%\order_product_edges.csv" ^
  --relationships=REPORTS_TO="%NEO4J_ADMIN%\employee_reports_to_edges.csv" ^
  --relationships=WROTE="%NEO4J_ADMIN%\customer_review_edges.csv" ^
  --relationships=ABOUT="%NEO4J_ADMIN%\review_product_edges.csv" ^
  --delimiter="," ^
  --array-delimiter=";" ^
  --skip-bad-relationships=true ^
  --skip-duplicate-nodes=true
