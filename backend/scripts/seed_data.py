#!/usr/bin/env python3
"""
Seed Script — Loads SAP O2C JSONL data into Neo4j.

Usage (inside Docker):
    docker-compose exec api python scripts/seed_data.py

Usage (locally):
    NEO4J_URI=bolt://localhost:7687 python scripts/seed_data.py
"""

import json
import os
import sys
import glob
import time
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

# ── Config ──────────────────────────────────────────────────────────
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "dodge_ai_2024")

# Dataset path — inside Docker it's mounted at /data/dataset
DATASET_DIR = Path(os.getenv("DATASET_DIR", "/data/dataset/sap-o2c-data"))
if not DATASET_DIR.exists():
    # Fallback for local development
    DATASET_DIR = Path(__file__).resolve().parent.parent.parent / "dataset" / "sap-o2c-data"

BATCH_SIZE = 500


# ── Helpers ─────────────────────────────────────────────────────────
def read_jsonl_folder(folder_name: str) -> list[dict]:
    """Read all .jsonl files in a dataset subfolder."""
    folder = DATASET_DIR / folder_name
    if not folder.exists():
        print(f"  ⚠️  Folder not found: {folder}")
        return []
    records = []
    for fpath in sorted(glob.glob(str(folder / "*.jsonl"))):
        with open(fpath, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
    return records


def run_batch(tx, query: str, rows: list[dict]):
    """Execute a parameterized Cypher query with a batch of rows."""
    tx.run(query, rows=rows)


def batch_execute(driver, query: str, data: list[dict], desc: str = ""):
    """Execute a query in batches."""
    total = len(data)
    if total == 0:
        print(f"  ⏭️  {desc}: no data, skipping")
        return
    with driver.session() as session:
        for i in range(0, total, BATCH_SIZE):
            batch = data[i : i + BATCH_SIZE]
            session.execute_write(run_batch, query, batch)
        print(f"  ✅ {desc}: {total} records")


# ── Create Constraints & Indexes ────────────────────────────────────
def create_constraints(driver):
    """Create uniqueness constraints and indexes for fast lookups."""
    constraints = [
        "CREATE CONSTRAINT IF NOT EXISTS FOR (n:SalesOrder) REQUIRE n.salesOrder IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Delivery) REQUIRE n.deliveryDocument IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (n:BillingDocument) REQUIRE n.billingDocument IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Customer) REQUIRE n.businessPartner IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Product) REQUIRE n.product IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Plant) REQUIRE n.plant IS UNIQUE",
    ]
    indexes = [
        "CREATE INDEX IF NOT EXISTS FOR (n:SalesOrderItem) ON (n.salesOrder, n.salesOrderItem)",
        "CREATE INDEX IF NOT EXISTS FOR (n:DeliveryItem) ON (n.deliveryDocument, n.deliveryDocumentItem)",
        "CREATE INDEX IF NOT EXISTS FOR (n:BillingDocumentItem) ON (n.billingDocument, n.billingDocumentItem)",
        "CREATE INDEX IF NOT EXISTS FOR (n:JournalEntry) ON (n.accountingDocument)",
        "CREATE INDEX IF NOT EXISTS FOR (n:Payment) ON (n.accountingDocument)",
        "CREATE INDEX IF NOT EXISTS FOR (n:DeliveryItem) ON (n.referenceSdDocument)",
        "CREATE INDEX IF NOT EXISTS FOR (n:BillingDocumentItem) ON (n.referenceSdDocument)",
        "CREATE INDEX IF NOT EXISTS FOR (n:JournalEntry) ON (n.referenceDocument)",
    ]
    with driver.session() as session:
        for stmt in constraints + indexes:
            session.run(stmt)
    print("✅ Constraints & indexes created")


# ── Load Nodes ──────────────────────────────────────────────────────
def load_nodes(driver):
    """Load all node types into Neo4j."""
    print("\n📦 Loading nodes...")

    # -- Sales Orders --
    data = read_jsonl_folder("sales_order_headers")
    batch_execute(driver, """
        UNWIND $rows AS row
        MERGE (n:SalesOrder {salesOrder: row.salesOrder})
        SET n.salesOrderType = row.salesOrderType,
            n.salesOrganization = row.salesOrganization,
            n.distributionChannel = row.distributionChannel,
            n.organizationDivision = row.organizationDivision,
            n.soldToParty = row.soldToParty,
            n.creationDate = row.creationDate,
            n.totalNetAmount = toFloat(row.totalNetAmount),
            n.overallDeliveryStatus = row.overallDeliveryStatus,
            n.transactionCurrency = row.transactionCurrency,
            n.requestedDeliveryDate = row.requestedDeliveryDate,
            n.incotermsClassification = row.incotermsClassification,
            n.customerPaymentTerms = row.customerPaymentTerms
    """, data, "SalesOrder")

    # -- Sales Order Items --
    data = read_jsonl_folder("sales_order_items")
    batch_execute(driver, """
        UNWIND $rows AS row
        MERGE (n:SalesOrderItem {salesOrder: row.salesOrder, salesOrderItem: row.salesOrderItem})
        SET n.salesOrderItemCategory = row.salesOrderItemCategory,
            n.material = row.material,
            n.requestedQuantity = toFloat(row.requestedQuantity),
            n.requestedQuantityUnit = row.requestedQuantityUnit,
            n.transactionCurrency = row.transactionCurrency,
            n.netAmount = toFloat(row.netAmount),
            n.materialGroup = row.materialGroup,
            n.productionPlant = row.productionPlant,
            n.storageLocation = row.storageLocation
    """, data, "SalesOrderItem")

    # -- Deliveries --
    data = read_jsonl_folder("outbound_delivery_headers")
    batch_execute(driver, """
        UNWIND $rows AS row
        MERGE (n:Delivery {deliveryDocument: row.deliveryDocument})
        SET n.creationDate = row.creationDate,
            n.overallGoodsMovementStatus = row.overallGoodsMovementStatus,
            n.overallPickingStatus = row.overallPickingStatus,
            n.shippingPoint = row.shippingPoint,
            n.deliveryBlockReason = row.deliveryBlockReason
    """, data, "Delivery")

    # -- Delivery Items --
    data = read_jsonl_folder("outbound_delivery_items")
    batch_execute(driver, """
        UNWIND $rows AS row
        MERGE (n:DeliveryItem {deliveryDocument: row.deliveryDocument, deliveryDocumentItem: row.deliveryDocumentItem})
        SET n.actualDeliveryQuantity = toFloat(row.actualDeliveryQuantity),
            n.deliveryQuantityUnit = row.deliveryQuantityUnit,
            n.plant = row.plant,
            n.referenceSdDocument = row.referenceSdDocument,
            n.referenceSdDocumentItem = row.referenceSdDocumentItem,
            n.storageLocation = row.storageLocation
    """, data, "DeliveryItem")

    # -- Billing Documents --
    data = read_jsonl_folder("billing_document_headers")
    batch_execute(driver, """
        UNWIND $rows AS row
        MERGE (n:BillingDocument {billingDocument: row.billingDocument})
        SET n.billingDocumentType = row.billingDocumentType,
            n.creationDate = row.creationDate,
            n.billingDocumentDate = row.billingDocumentDate,
            n.billingDocumentIsCancelled = row.billingDocumentIsCancelled,
            n.cancelledBillingDocument = row.cancelledBillingDocument,
            n.totalNetAmount = toFloat(row.totalNetAmount),
            n.transactionCurrency = row.transactionCurrency,
            n.companyCode = row.companyCode,
            n.fiscalYear = row.fiscalYear,
            n.accountingDocument = row.accountingDocument,
            n.soldToParty = row.soldToParty
    """, data, "BillingDocument")

    # -- Billing Document Items --
    data = read_jsonl_folder("billing_document_items")
    batch_execute(driver, """
        UNWIND $rows AS row
        MERGE (n:BillingDocumentItem {billingDocument: row.billingDocument, billingDocumentItem: row.billingDocumentItem})
        SET n.material = row.material,
            n.billingQuantity = toFloat(row.billingQuantity),
            n.billingQuantityUnit = row.billingQuantityUnit,
            n.netAmount = toFloat(row.netAmount),
            n.transactionCurrency = row.transactionCurrency,
            n.referenceSdDocument = row.referenceSdDocument,
            n.referenceSdDocumentItem = row.referenceSdDocumentItem
    """, data, "BillingDocumentItem")

    # -- Journal Entries --
    data = read_jsonl_folder("journal_entry_items_accounts_receivable")
    batch_execute(driver, """
        UNWIND $rows AS row
        MERGE (n:JournalEntry {
            companyCode: row.companyCode,
            fiscalYear: row.fiscalYear,
            accountingDocument: row.accountingDocument,
            accountingDocumentItem: row.accountingDocumentItem
        })
        SET n.glAccount = row.glAccount,
            n.referenceDocument = row.referenceDocument,
            n.profitCenter = row.profitCenter,
            n.transactionCurrency = row.transactionCurrency,
            n.amountInTransactionCurrency = toFloat(row.amountInTransactionCurrency),
            n.postingDate = row.postingDate,
            n.documentDate = row.documentDate,
            n.accountingDocumentType = row.accountingDocumentType,
            n.customer = row.customer,
            n.financialAccountType = row.financialAccountType,
            n.clearingDate = row.clearingDate,
            n.clearingAccountingDocument = row.clearingAccountingDocument
    """, data, "JournalEntry")

    # -- Payments --
    data = read_jsonl_folder("payments_accounts_receivable")
    batch_execute(driver, """
        UNWIND $rows AS row
        MERGE (n:Payment {
            companyCode: row.companyCode,
            fiscalYear: row.fiscalYear,
            accountingDocument: row.accountingDocument,
            accountingDocumentItem: row.accountingDocumentItem
        })
        SET n.clearingDate = row.clearingDate,
            n.clearingAccountingDocument = row.clearingAccountingDocument,
            n.amountInTransactionCurrency = toFloat(row.amountInTransactionCurrency),
            n.transactionCurrency = row.transactionCurrency,
            n.customer = row.customer,
            n.postingDate = row.postingDate,
            n.documentDate = row.documentDate,
            n.glAccount = row.glAccount,
            n.financialAccountType = row.financialAccountType,
            n.profitCenter = row.profitCenter
    """, data, "Payment")

    # -- Customers --
    data = read_jsonl_folder("business_partners")
    batch_execute(driver, """
        UNWIND $rows AS row
        MERGE (n:Customer {businessPartner: row.businessPartner})
        SET n.customer = row.customer,
            n.businessPartnerFullName = row.businessPartnerFullName,
            n.businessPartnerName = row.businessPartnerName,
            n.businessPartnerCategory = row.businessPartnerCategory,
            n.creationDate = row.creationDate
    """, data, "Customer")

    # -- Products --
    data = read_jsonl_folder("products")
    # Also load descriptions
    desc_data = read_jsonl_folder("product_descriptions")
    desc_map = {}
    for d in desc_data:
        if d.get("language") == "EN":
            desc_map[d["product"]] = d.get("productDescription", "")
    for rec in data:
        rec["productDescription"] = desc_map.get(rec["product"], "")

    batch_execute(driver, """
        UNWIND $rows AS row
        MERGE (n:Product {product: row.product})
        SET n.productType = row.productType,
            n.grossWeight = toFloat(row.grossWeight),
            n.weightUnit = row.weightUnit,
            n.netWeight = toFloat(row.netWeight),
            n.productGroup = row.productGroup,
            n.baseUnit = row.baseUnit,
            n.division = row.division,
            n.productDescription = row.productDescription
    """, data, "Product")

    # -- Plants --
    data = read_jsonl_folder("plants")
    batch_execute(driver, """
        UNWIND $rows AS row
        MERGE (n:Plant {plant: row.plant})
        SET n.plantName = row.plantName,
            n.valuationArea = row.valuationArea,
            n.salesOrganization = row.salesOrganization,
            n.distributionChannel = row.distributionChannel,
            n.division = row.division
    """, data, "Plant")


# ── Load Relationships ──────────────────────────────────────────────
def load_relationships(driver):
    """Create all relationships between existing nodes."""
    print("\n🔗 Creating relationships...")

    with driver.session() as session:
        # 1. SalesOrder -[HAS_ITEM]-> SalesOrderItem
        result = session.run("""
            MATCH (so:SalesOrder), (soi:SalesOrderItem)
            WHERE so.salesOrder = soi.salesOrder
            MERGE (so)-[:HAS_ITEM]->(soi)
            RETURN count(*) AS cnt
        """)
        print(f"  ✅ SalesOrder -[HAS_ITEM]-> SalesOrderItem: {result.single()['cnt']}")

        # 2. SalesOrderItem -[CONTAINS_PRODUCT]-> Product
        result = session.run("""
            MATCH (soi:SalesOrderItem), (p:Product)
            WHERE soi.material = p.product
            MERGE (soi)-[:CONTAINS_PRODUCT]->(p)
            RETURN count(*) AS cnt
        """)
        print(f"  ✅ SalesOrderItem -[CONTAINS_PRODUCT]-> Product: {result.single()['cnt']}")

        # 3. SalesOrder -[SOLD_TO]-> Customer
        result = session.run("""
            MATCH (so:SalesOrder), (c:Customer)
            WHERE so.soldToParty = c.businessPartner
            MERGE (so)-[:SOLD_TO]->(c)
            RETURN count(*) AS cnt
        """)
        print(f"  ✅ SalesOrder -[SOLD_TO]-> Customer: {result.single()['cnt']}")

        # 4. Delivery -[HAS_ITEM]-> DeliveryItem
        result = session.run("""
            MATCH (d:Delivery), (di:DeliveryItem)
            WHERE d.deliveryDocument = di.deliveryDocument
            MERGE (d)-[:HAS_ITEM]->(di)
            RETURN count(*) AS cnt
        """)
        print(f"  ✅ Delivery -[HAS_ITEM]-> DeliveryItem: {result.single()['cnt']}")

        # 5. DeliveryItem -[FULFILLS]-> SalesOrderItem
        result = session.run("""
            MATCH (di:DeliveryItem), (soi:SalesOrderItem)
            WHERE di.referenceSdDocument = soi.salesOrder
              AND di.referenceSdDocumentItem = soi.salesOrderItem
            MERGE (di)-[:FULFILLS]->(soi)
            RETURN count(*) AS cnt
        """)
        print(f"  ✅ DeliveryItem -[FULFILLS]-> SalesOrderItem: {result.single()['cnt']}")

        # 6. DeliveryItem -[SHIPPED_FROM]-> Plant
        result = session.run("""
            MATCH (di:DeliveryItem), (p:Plant)
            WHERE di.plant = p.plant
            MERGE (di)-[:SHIPPED_FROM]->(p)
            RETURN count(*) AS cnt
        """)
        print(f"  ✅ DeliveryItem -[SHIPPED_FROM]-> Plant: {result.single()['cnt']}")

        # 7. BillingDocument -[HAS_ITEM]-> BillingDocumentItem
        result = session.run("""
            MATCH (bd:BillingDocument), (bdi:BillingDocumentItem)
            WHERE bd.billingDocument = bdi.billingDocument
            MERGE (bd)-[:HAS_ITEM]->(bdi)
            RETURN count(*) AS cnt
        """)
        print(f"  ✅ BillingDocument -[HAS_ITEM]-> BillingDocumentItem: {result.single()['cnt']}")

        # 8. BillingDocumentItem -[BILLS]-> DeliveryItem
        result = session.run("""
            MATCH (bdi:BillingDocumentItem), (di:DeliveryItem)
            WHERE bdi.referenceSdDocument = di.deliveryDocument
              AND bdi.referenceSdDocumentItem = di.deliveryDocumentItem
            MERGE (bdi)-[:BILLS]->(di)
            RETURN count(*) AS cnt
        """)
        print(f"  ✅ BillingDocumentItem -[BILLS]-> DeliveryItem: {result.single()['cnt']}")

        # 9. BillingDocument -[SOLD_TO]-> Customer
        result = session.run("""
            MATCH (bd:BillingDocument), (c:Customer)
            WHERE bd.soldToParty = c.businessPartner
            MERGE (bd)-[:SOLD_TO]->(c)
            RETURN count(*) AS cnt
        """)
        print(f"  ✅ BillingDocument -[SOLD_TO]-> Customer: {result.single()['cnt']}")

        # 10. BillingDocument -[GENERATES_JOURNAL]-> JournalEntry
        #     Link via accountingDocument (the billing doc's accounting doc = journal's accounting doc)
        result = session.run("""
            MATCH (bd:BillingDocument), (je:JournalEntry)
            WHERE bd.accountingDocument = je.accountingDocument
              AND bd.companyCode = je.companyCode
              AND bd.fiscalYear = je.fiscalYear
            MERGE (bd)-[:GENERATES_JOURNAL]->(je)
            RETURN count(*) AS cnt
        """)
        print(f"  ✅ BillingDocument -[GENERATES_JOURNAL]-> JournalEntry: {result.single()['cnt']}")

        # 11. JournalEntry -[CLEARED_BY]-> Payment
        result = session.run("""
            MATCH (je:JournalEntry), (pay:Payment)
            WHERE je.clearingAccountingDocument IS NOT NULL
              AND je.clearingAccountingDocument <> ''
              AND je.clearingAccountingDocument = pay.accountingDocument
              AND je.companyCode = pay.companyCode
            MERGE (je)-[:CLEARED_BY]->(pay)
            RETURN count(*) AS cnt
        """)
        print(f"  ✅ JournalEntry -[CLEARED_BY]-> Payment: {result.single()['cnt']}")

        # 12. Product -[PRODUCED_AT]-> Plant (via product_plants)
        pp_data = read_jsonl_folder("product_plants")
        if pp_data:
            # Use batch approach for this one
            session.run("""
                UNWIND $rows AS row
                MATCH (prod:Product {product: row.product})
                MATCH (pl:Plant {plant: row.plant})
                MERGE (prod)-[:PRODUCED_AT]->(pl)
            """, rows=pp_data)
            print(f"  ✅ Product -[PRODUCED_AT]-> Plant: {len(pp_data)} links")


# ── Summary ─────────────────────────────────────────────────────────
def print_summary(driver):
    """Print node and relationship counts."""
    print("\n📊 Graph Summary:")
    with driver.session() as session:
        # Node counts
        result = session.run("""
            MATCH (n)
            RETURN labels(n)[0] AS label, count(n) AS count
            ORDER BY count DESC
        """)
        for record in result:
            print(f"  {record['label']}: {record['count']} nodes")

        # Relationship counts
        result = session.run("""
            MATCH ()-[r]->()
            RETURN type(r) AS type, count(r) AS count
            ORDER BY count DESC
        """)
        print()
        for record in result:
            print(f"  [{record['type']}]: {record['count']} relationships")

        # Total
        result = session.run("MATCH (n) RETURN count(n) AS nodes")
        total_nodes = result.single()["nodes"]
        result = session.run("MATCH ()-[r]->() RETURN count(r) AS rels")
        total_rels = result.single()["rels"]
        print(f"\n  Total: {total_nodes} nodes, {total_rels} relationships")


# ── Main ────────────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("🚀 Dodge AI — Neo4j Data Ingestion")
    print("=" * 60)
    print(f"  Neo4j: {NEO4J_URI}")
    print(f"  Dataset: {DATASET_DIR}")
    print()

    if not DATASET_DIR.exists():
        print(f"❌ Dataset directory not found: {DATASET_DIR}")
        sys.exit(1)

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    try:
        driver.verify_connectivity()
        print("✅ Connected to Neo4j\n")

        t0 = time.time()
        create_constraints(driver)
        load_nodes(driver)
        load_relationships(driver)
        elapsed = time.time() - t0

        print_summary(driver)
        print(f"\n⏱️  Completed in {elapsed:.1f}s")
        print("=" * 60)
    finally:
        driver.close()


if __name__ == "__main__":
    main()
