import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/db";

export async function GET(req: NextRequest) {
  const documentId = Number(req.nextUrl.searchParams.get("documentId"));
  if (!documentId || isNaN(documentId)) {
    return NextResponse.json({ error: "documentId is required" }, { status: 400 });
  }

  const items = await prisma.budgetItem.findMany({
    where: { documentId },
    include: {
      category: {
        select: { code: true, description: true, level: true, parentId: true },
      },
    },
    orderBy: { id: "asc" },
  });

  return NextResponse.json(items);
}
