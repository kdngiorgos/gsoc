import { NextResponse } from "next/server";
import { prisma } from "@/lib/db";

export async function GET() {
  const documents = await prisma.document.findMany({
    orderBy: { importedAt: "desc" },
    select: {
      id: true,
      filename: true,
      docType: true,
      municipality: true,
      year: true,
      importedAt: true,
      _count: {
        select: {
          budgetItems: true,
          projects: true,
        },
      },
    },
  });
  return NextResponse.json(documents);
}
