import { ethers } from "hardhat";
import * as fs from "fs";
import * as path from "path";

async function main() {
  console.log("Deploying AssessmentRegistry smart contract...");
  const AssessmentRegistry = await ethers.getContractFactory("AssessmentRegistry");
  const registry = await AssessmentRegistry.deploy();
  await registry.waitForDeployment();

  const contractAddress = await registry.getAddress();
  console.log(`AssessmentRegistry successfully deployed to: ${contractAddress}`);

  // Export contract address & ABI info for backend
  const exportPath = path.join(__dirname, "../contract_info.json");
  const contractInfo = {
    address: contractAddress,
    network: "sepolia",
    deployedAt: new Date().toISOString()
  };
  fs.writeFileSync(exportPath, JSON.stringify(contractInfo, null, 2));
  console.log(`Contract info exported to: ${exportPath}`);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
