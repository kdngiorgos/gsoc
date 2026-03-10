-- Drop old tables (data discarded — PoC with test data only)
DROP TABLE IF EXISTS "TechnicalProjectItem";
DROP TABLE IF EXISTS "TechnicalProject";
DROP TABLE IF EXISTS "BudgetItem";
DROP TABLE IF EXISTS "BudgetCategory";

-- Remove old relation columns from Document (they no longer exist as FK targets)
-- (No explicit FK columns on Document; relations were on child tables)

-- Create unified Item table
CREATE TABLE "Item" (
    "id"          SERIAL PRIMARY KEY,
    "documentId"  INTEGER NOT NULL,
    "code"        TEXT NOT NULL,
    "description" TEXT NOT NULL,
    "parentCode"  TEXT,
    CONSTRAINT "Item_documentId_fkey" FOREIGN KEY ("documentId") REFERENCES "Document"("id") ON DELETE RESTRICT ON UPDATE CASCADE
);

-- Create ItemAmount table
CREATE TABLE "ItemAmount" (
    "id"     SERIAL PRIMARY KEY,
    "itemId" INTEGER NOT NULL,
    "label"  TEXT NOT NULL,
    "amount" DECIMAL(15,2) NOT NULL,
    CONSTRAINT "ItemAmount_itemId_fkey" FOREIGN KEY ("itemId") REFERENCES "Item"("id") ON DELETE RESTRICT ON UPDATE CASCADE
);
