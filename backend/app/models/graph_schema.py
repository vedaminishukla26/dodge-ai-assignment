"""
Neo4j Graph Schema for SAP Order-to-Cash data.
Defines node labels, their properties, and relationship types.
This serves as both documentation and runtime schema reference for the LLM.
"""

# ── Node Definitions ────────────────────────────────────────────────
# Each entry: label → (primary_key_field, description, source_folder)

NODE_DEFINITIONS = {
    "SalesOrder": {
        "pk": "salesOrder",
        "description": "A sales order header with pricing, status, and customer info",
        "source": "sales_order_headers",
        "properties": [
            "salesOrder", "salesOrderType", "salesOrganization",
            "distributionChannel", "organizationDivision",
            "soldToParty", "creationDate", "totalNetAmount",
            "overallDeliveryStatus", "transactionCurrency",
            "requestedDeliveryDate", "incotermsClassification",
            "customerPaymentTerms",
        ],
    },
    "SalesOrderItem": {
        "pk": ["salesOrder", "salesOrderItem"],
        "description": "A line item within a sales order, referencing a material",
        "source": "sales_order_items",
        "properties": [
            "salesOrder", "salesOrderItem", "salesOrderItemCategory",
            "material", "requestedQuantity", "requestedQuantityUnit",
            "transactionCurrency", "netAmount", "materialGroup",
            "productionPlant", "storageLocation",
        ],
    },
    "Delivery": {
        "pk": "deliveryDocument",
        "description": "An outbound delivery document for shipping goods",
        "source": "outbound_delivery_headers",
        "properties": [
            "deliveryDocument", "creationDate",
            "overallGoodsMovementStatus", "overallPickingStatus",
            "shippingPoint", "deliveryBlockReason",
        ],
    },
    "DeliveryItem": {
        "pk": ["deliveryDocument", "deliveryDocumentItem"],
        "description": "A line item in a delivery, linking back to a sales order",
        "source": "outbound_delivery_items",
        "properties": [
            "deliveryDocument", "deliveryDocumentItem",
            "actualDeliveryQuantity", "deliveryQuantityUnit",
            "plant", "referenceSdDocument", "referenceSdDocumentItem",
            "storageLocation",
        ],
    },
    "BillingDocument": {
        "pk": "billingDocument",
        "description": "An invoice / billing document",
        "source": "billing_document_headers",
        "properties": [
            "billingDocument", "billingDocumentType", "creationDate",
            "billingDocumentDate", "billingDocumentIsCancelled",
            "cancelledBillingDocument", "totalNetAmount",
            "transactionCurrency", "companyCode", "fiscalYear",
            "accountingDocument", "soldToParty",
        ],
    },
    "BillingDocumentItem": {
        "pk": ["billingDocument", "billingDocumentItem"],
        "description": "A line item in a billing document",
        "source": "billing_document_items",
        "properties": [
            "billingDocument", "billingDocumentItem", "material",
            "billingQuantity", "billingQuantityUnit", "netAmount",
            "transactionCurrency", "referenceSdDocument",
            "referenceSdDocumentItem",
        ],
    },
    "JournalEntry": {
        "pk": ["companyCode", "fiscalYear", "accountingDocument", "accountingDocumentItem"],
        "description": "An accounting journal entry (accounts receivable)",
        "source": "journal_entry_items_accounts_receivable",
        "properties": [
            "companyCode", "fiscalYear", "accountingDocument",
            "accountingDocumentItem", "glAccount",
            "referenceDocument", "profitCenter",
            "transactionCurrency", "amountInTransactionCurrency",
            "postingDate", "documentDate", "accountingDocumentType",
            "customer", "financialAccountType",
            "clearingDate", "clearingAccountingDocument",
        ],
    },
    "Payment": {
        "pk": ["companyCode", "fiscalYear", "accountingDocument", "accountingDocumentItem"],
        "description": "A payment record for accounts receivable",
        "source": "payments_accounts_receivable",
        "properties": [
            "companyCode", "fiscalYear", "accountingDocument",
            "accountingDocumentItem",
            "clearingDate", "clearingAccountingDocument",
            "amountInTransactionCurrency", "transactionCurrency",
            "customer", "postingDate", "documentDate",
            "glAccount", "financialAccountType", "profitCenter",
        ],
    },
    "Customer": {
        "pk": "businessPartner",
        "description": "A business partner / customer",
        "source": "business_partners",
        "properties": [
            "businessPartner", "customer",
            "businessPartnerFullName", "businessPartnerName",
            "businessPartnerCategory", "creationDate",
        ],
    },
    "Product": {
        "pk": "product",
        "description": "A product / material master",
        "source": "products",
        "properties": [
            "product", "productType", "grossWeight", "weightUnit",
            "netWeight", "productGroup", "baseUnit", "division",
        ],
    },
    "Plant": {
        "pk": "plant",
        "description": "A manufacturing / distribution plant",
        "source": "plants",
        "properties": [
            "plant", "plantName", "valuationArea",
            "salesOrganization", "distributionChannel", "division",
        ],
    },
}


# ── Relationship Definitions ────────────────────────────────────────
# (from_label, rel_type, to_label, description, join_logic_hint)

RELATIONSHIP_DEFINITIONS = [
    {
        "from": "SalesOrder",
        "type": "HAS_ITEM",
        "to": "SalesOrderItem",
        "description": "A sales order contains line items",
        "join": "SalesOrder.salesOrder = SalesOrderItem.salesOrder",
    },
    {
        "from": "SalesOrderItem",
        "type": "CONTAINS_PRODUCT",
        "to": "Product",
        "description": "A sales order item references a product/material",
        "join": "SalesOrderItem.material = Product.product",
    },
    {
        "from": "SalesOrder",
        "type": "SOLD_TO",
        "to": "Customer",
        "description": "A sales order is sold to a customer",
        "join": "SalesOrder.soldToParty = Customer.businessPartner",
    },
    {
        "from": "DeliveryItem",
        "type": "FULFILLS",
        "to": "SalesOrderItem",
        "description": "A delivery item fulfills a sales order item",
        "join": "DeliveryItem.referenceSdDocument = SalesOrderItem.salesOrder AND DeliveryItem.referenceSdDocumentItem = SalesOrderItem.salesOrderItem",
    },
    {
        "from": "Delivery",
        "type": "HAS_ITEM",
        "to": "DeliveryItem",
        "description": "A delivery contains delivery line items",
        "join": "Delivery.deliveryDocument = DeliveryItem.deliveryDocument",
    },
    {
        "from": "DeliveryItem",
        "type": "SHIPPED_FROM",
        "to": "Plant",
        "description": "A delivery item is shipped from a plant",
        "join": "DeliveryItem.plant = Plant.plant",
    },
    {
        "from": "BillingDocumentItem",
        "type": "BILLS",
        "to": "DeliveryItem",
        "description": "A billing item bills a delivery item",
        "join": "BillingDocumentItem.referenceSdDocument = DeliveryItem.deliveryDocument AND BillingDocumentItem.referenceSdDocumentItem = DeliveryItem.deliveryDocumentItem",
    },
    {
        "from": "BillingDocument",
        "type": "HAS_ITEM",
        "to": "BillingDocumentItem",
        "description": "A billing document contains billing line items",
        "join": "BillingDocument.billingDocument = BillingDocumentItem.billingDocument",
    },
    {
        "from": "BillingDocument",
        "type": "SOLD_TO",
        "to": "Customer",
        "description": "A billing document is billed to a customer",
        "join": "BillingDocument.soldToParty = Customer.businessPartner",
    },
    {
        "from": "BillingDocument",
        "type": "GENERATES_JOURNAL",
        "to": "JournalEntry",
        "description": "A billing document generates accounting journal entries",
        "join": "BillingDocument.accountingDocument = JournalEntry.accountingDocument AND BillingDocument.companyCode = JournalEntry.companyCode AND BillingDocument.fiscalYear = JournalEntry.fiscalYear",
    },
    {
        "from": "JournalEntry",
        "type": "CLEARED_BY",
        "to": "Payment",
        "description": "A journal entry is cleared by a payment",
        "join": "JournalEntry.clearingAccountingDocument = Payment.accountingDocument AND JournalEntry.companyCode = Payment.companyCode",
    },
    {
        "from": "Product",
        "type": "PRODUCED_AT",
        "to": "Plant",
        "description": "A product is produced/stored at a plant",
        "join": "via product_plants table: product_plants.product = Product.product AND product_plants.plant = Plant.plant",
    },
]


def get_schema_description() -> str:
    """Generate a human-readable schema description for LLM prompting."""
    lines = ["=== SAP Order-to-Cash Graph Schema ===", ""]
    lines.append("## Node Types:")
    for label, defn in NODE_DEFINITIONS.items():
        pk = defn["pk"] if isinstance(defn["pk"], str) else " + ".join(defn["pk"])
        props = ", ".join(defn["properties"])
        lines.append(f"  ({label}) — {defn['description']}")
        lines.append(f"    Primary Key: {pk}")
        lines.append(f"    Properties: {props}")
        lines.append("")

    lines.append("## Relationships:")
    for rel in RELATIONSHIP_DEFINITIONS:
        lines.append(
            f"  (:{rel['from']})-[:{rel['type']}]->(:{rel['to']})  — {rel['description']}"
        )
    lines.append("")

    lines.append("## O2C Flow:")
    lines.append(
        "  SalesOrder -[HAS_ITEM]-> SalesOrderItem -[fulfilled by DeliveryItem via FULFILLS]-> "
        "Delivery -[billed by BillingDocumentItem via BILLS]-> BillingDocument "
        "-[GENERATES_JOURNAL]-> JournalEntry -[CLEARED_BY]-> Payment"
    )
    return "\n".join(lines)

if __name__ == "__main__":
    print(get_schema_description())
