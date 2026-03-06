import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/db";

export async function GET(req: NextRequest) {
  const documentId = Number(req.nextUrl.searchParams.get("documentId"));
  if (!documentId || isNaN(documentId)) {
    return NextResponse.json({ error: "documentId is required" }, { status: 400 });
  }

  const projects = await prisma.technicalProject.findMany({
    where: { documentId },
    include: { items: true },
    orderBy: [{ section: "asc" }, { id: "asc" }],
  });

  return NextResponse.json(projects);
}
