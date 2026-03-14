import { prisma } from "@/lib/db";
import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  const q = req.nextUrl.searchParams.get("q")?.trim() ?? "";
  if (q.length < 2) return NextResponse.json([]);

  const items = await prisma.item.findMany({
    where: { description: { contains: q, mode: "insensitive" } },
    include: {
      amounts: true,
      document: {
        select: { id: true, filename: true, municipality: true, year: true, docType: true },
      },
    },
    orderBy: { id: "asc" },
    take: 100,
  });

  return NextResponse.json(items);
}
