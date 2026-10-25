-- CreateTable
CREATE TABLE "Member" (
    "id" TEXT NOT NULL,
    "dateOfBirth" TIMESTAMP(3),
    "credit_card" TEXT,

    CONSTRAINT "Member_pkey" PRIMARY KEY ("id")
);
