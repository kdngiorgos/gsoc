import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/db";

export async function GET(req: NextRequest) {
  const params = req.nextUrl.searchParams;
  const documentId = Number(params.get("documentId"));
  if (!documentId || isNaN(documentId)) {
    return NextResponse.json({ error: "documentId is required" }, { status: 400 });
  }

  const page = Math.max(1, parseInt(params.get("page") ?? "1", 10) || 1);
  const limit = Math.min(200, Math.max(1, parseInt(params.get("limit") ?? "50", 10) || 50));
  const skip = (page - 1) * limit;

  const [items, total] = await Promise.all([
    prisma.item.findMany({
      where: { documentId },
      include: { amounts: true },
      orderBy: { id: "asc" },
      skip,
      take: limit,
    }),
    prisma.item.count({ where: { documentId } }),
  ]);

  return NextResponse.json({ data: items, total, page, limit });
}
