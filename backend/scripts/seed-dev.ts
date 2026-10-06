import { prisma } from "../src/database/prisma";

async function main() {
  const organization = await prisma.organization.upsert({
    where: {
      slug: "truthchain-dev",
    },
    update: {},
    create: {
      name: "TruthChain Development",
      slug: "truthchain-dev",
    },
  });

  console.log("Development organization:");
  console.log({
    id: organization.id,
    name: organization.name,
    slug: organization.slug,
    status: organization.status,
  });
}

main()
  .catch((error) => {
    console.error("Seed failed:", error);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });