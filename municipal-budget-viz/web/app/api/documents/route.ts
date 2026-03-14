import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/db";

export async function GET(req: NextRequest) {
  const params = req.nextUrl.searchParams;
  const page = Math.max(1, parseInt(params.get("page") ?? "1", 10) || 1);
  const limit = Math.min(100, Math.max(1, parseInt(params.get("limit") ?? "20", 10) || 20));
  const skip = (page - 1) * limit;

  const [documents, total] = await Promise.all([
    prisma.document.findMany({
      orderBy: { importedAt: "desc" },
      skip,
      take: limit,
      select: {
        id: true,
        filename: true,
        docType: true,
        municipality: true,
        year: true,
        importedAt: true,
        _count: { select: { items: true } },
      },
    }),
    prisma.document.count(),
  ]);

  return NextResponse.json({ data: documents, total, page, limit });
}
