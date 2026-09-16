// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract EvidenceRegistry {
    struct Evidence {
        address reporter;
        bytes32 cid;
        uint256 timestamp;
        uint32 fraudScore;
        string status; // PENDING, VERIFIED, REJECTED, REVIEW_REQUIRED
    }

    mapping(bytes32 => Evidence) public records; // key = claimId

    event ClaimSubmitted(bytes32 indexed claimId, address indexed submitter, uint256 timestamp);
    event ClaimVerified(bytes32 indexed claimId, string status, uint32 fraudScore);
    event DuplicateImageDetected(bytes32 indexed oldClaimId, bytes32 indexed newClaimId);

    function storeEvidence(
        bytes32 claimId,
        bytes32 contentCid,
        uint32 fraudScore,
        string calldata status
    ) external {
        require(records[claimId].timestamp == 0, "Evidence for this claim already exists");
        
        records[claimId] = Evidence({
            reporter: msg.sender,
            cid: contentCid,
            timestamp: block.timestamp,
            fraudScore: fraudScore,
            status: status
        });

        emit ClaimSubmitted(claimId, msg.sender, block.timestamp);
        emit ClaimVerified(claimId, status, fraudScore);
    }

    function emitDuplicate(bytes32 oldClaimId, bytes32 newClaimId) external {
        emit DuplicateImageDetected(oldClaimId, newClaimId);
    }

    function getEvidence(bytes32 claimId) external view returns (
        address reporter,
        bytes32 cid,
        uint256 timestamp,
        uint32 fraudScore,
        string memory status
    ) {
        Evidence memory ev = records[claimId];
        require(ev.timestamp > 0, "Claim does not exist");
        return (ev.reporter, ev.cid, ev.timestamp, ev.fraudScore, ev.status);
    }
}
