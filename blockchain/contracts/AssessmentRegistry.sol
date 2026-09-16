// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title AssessmentRegistry
 * @dev TruthChain Audit & Verification Layer
 * Stores lightweight cryptographic commitments (image hash & canonical prediction hash)
 * off-chain vehicle damage assessment results without embedding business/ML logic on-chain.
 */
contract AssessmentRegistry {
    struct Assessment {
        bytes32 imageHash;
        bytes32 predictionHash;
        string modelVersion;
        uint256 timestamp;
        address recorder;
    }

    // Mapping from unique record identifier (e.g. TC-000001 or SHA256 recordId) to Assessment
    mapping(bytes32 => Assessment) public assessments;

    // Track total registered assessments
    uint256 public totalAssessments;

    event AssessmentRegistered(
        bytes32 indexed recordId,
        bytes32 indexed imageHash,
        bytes32 predictionHash,
        string modelVersion,
        uint256 timestamp,
        address recorder
    );

    /**
     * @notice Register a new vehicle damage assessment commitment on-chain.
     * @param recordId Unique identifier for the assessment record.
     * @param imageHash SHA-256 hash of the original vehicle image.
     * @param predictionHash SHA-256 hash of the canonical prediction JSON.
     * @param modelVersion Identifier/version string of the vision model used.
     */
    function registerAssessment(
        bytes32 recordId,
        bytes32 imageHash,
        bytes32 predictionHash,
        string calldata modelVersion
    ) external {
        require(assessments[recordId].timestamp == 0, "Assessment already registered for this record ID");
        require(imageHash != bytes32(0), "Image hash cannot be zero");
        require(predictionHash != bytes32(0), "Prediction hash cannot be zero");

        assessments[recordId] = Assessment({
            imageHash: imageHash,
            predictionHash: predictionHash,
            modelVersion: modelVersion,
            timestamp: block.timestamp,
            recorder: msg.sender
        });

        totalAssessments++;

        emit AssessmentRegistered(
            recordId,
            imageHash,
            predictionHash,
            modelVersion,
            block.timestamp,
            msg.sender
        );
    }

    /**
     * @notice Retrieve the registered assessment details for a given record ID.
     */
    function getAssessment(bytes32 recordId) external view returns (
        bytes32 imageHash,
        bytes32 predictionHash,
        string memory modelVersion,
        uint256 timestamp,
        address recorder
    ) {
        Assessment memory a = assessments[recordId];
        require(a.timestamp > 0, "Assessment not found");
        return (a.imageHash, a.predictionHash, a.modelVersion, a.timestamp, a.recorder);
    }

    /**
     * @notice Cryptographically verify if given image and prediction hashes match the on-chain record.
     */
    function verifyAssessment(
        bytes32 recordId,
        bytes32 imageHash,
        bytes32 predictionHash
    ) external view returns (bool isMatch, uint256 registeredAt) {
        Assessment memory a = assessments[recordId];
        if (a.timestamp == 0) {
            return (false, 0);
        }
        bool matches = (a.imageHash == imageHash && a.predictionHash == predictionHash);
        return (matches, a.timestamp);
    }
}
