const hre = require("hardhat");
const fs = require("fs");
const path = require("path");

async function main() {
  console.log("Memulai deployment ConcertTicketing...");

  const ContractFactory = await hre.ethers.getContractFactory("ConcertTicketing");

  // Constructor tidak membutuhkan argumen (deployer otomatis menjadi promotor)
  const contract = await ContractFactory.deploy();

  await contract.waitForDeployment();

  const contractAddress = await contract.getAddress();

  console.log("Deployment berhasil!");
  console.log("Alamat kontrak:", contractAddress);

  // Simpan alamat kontrak ke deployment.json
  const deploymentData = {
    contractName: "ConcertTicketing",
    address: contractAddress,
    network: "localhost",
    chainId: 31337,
  };

  const deploymentPath = path.join(__dirname, "..", "deployment.json");

  fs.writeFileSync(deploymentPath, JSON.stringify(deploymentData, null, 2));

  console.log("Alamat kontrak disimpan ke deployment.json");
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
