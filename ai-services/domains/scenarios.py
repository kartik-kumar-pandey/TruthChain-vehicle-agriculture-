# TruthChain 2.0 Scenario Database

SCENARIOS = {
    "motor": [
        {
            "id": "motor_genuine",
            "name": "Genuine Accident Claim",
            "description": "A standard auto accident with matching telematics and image evidence.",
            "data": {
                "claim_text": "Rear-end collision at traffic light. Car stopped suddenly in front.",
                "image_url": "https://images.unsplash.com/photo-1594913785162-e67853827cb6",
                "image_metadata": {"camera": "Dashcam V3", "timestamp": "2026-08-24T14:15:00Z"},
                "imu_data": {"acceleration_peak_g": 3.8, "speed_drop_kph": 30.0},
                "gps_data": {"claimed_coords": "26.4499,80.3319", "log_coords": "26.4499,80.3319"},
                "license_plate": "UP78AB1234",
                "owner_info": "Kartik Kumar"
            }
        },
        {
            "id": "motor_staged",
            "name": "Staged Accident (GPS Mismatch)",
            "description": "Claimed accident location does not match the actual GPS log from the vehicle's telematics.",
            "data": {
                "claim_text": "Hit a concrete divider on NH-2 near Kanpur.",
                "image_url": "https://images.unsplash.com/photo-1606577924006-27d39b133907",
                "image_metadata": {"camera": "iPhone 15", "timestamp": "2026-08-20T10:00:00Z"},
                "imu_data": {"acceleration_peak_g": 4.1, "speed_drop_kph": 45.0},
                "gps_data": {"claimed_coords": "26.4499,80.3319", "log_coords": "28.6139,77.2090"}, # Kanpur vs Delhi
                "license_plate": "UP78CD5678",
                "owner_info": "Moksh Gupta"
            }
        },
        {
            "id": "motor_duplicate",
            "name": "Reused Crash Photo (Duplicate Image)",
            "description": "The submitted photo is identified as a duplicate of an earlier claim filed with another insurer.",
            "data": {
                "claim_text": "Flipped vehicle due to tyre burst on highway.",
                "image_url": "https://images.unsplash.com/photo-1594913785162-e67853827cb6", # Reuse genuine crash image
                "image_metadata": {"camera": "Unknown", "timestamp": "2026-08-15T08:30:00Z"},
                "imu_data": {"acceleration_peak_g": 0.5, "speed_drop_kph": 5.0},
                "gps_data": {"claimed_coords": "26.4499,80.3319", "log_coords": "26.4499,80.3319"},
                "license_plate": "UP78EF9012",
                "owner_info": "Krishna Gupta"
            }
        },
        {
            "id": "motor_sensor_manipulation",
            "name": "Sensor Manipulation (Low Impact Anomaly)",
            "description": "Claim narrative claims a high-speed crash, but telematics logs show near-zero acceleration peaks.",
            "data": {
                "claim_text": "Total loss crash with high-speed impact at 60 km/h.",
                "image_url": "https://images.unsplash.com/photo-1617469767053-d3b508a04209",
                "image_metadata": {"camera": "OnePlus 12", "timestamp": "2026-08-22T19:45:00Z"},
                "imu_data": {"acceleration_peak_g": 0.2, "speed_drop_kph": 1.5}, # Faked/Spliced log
                "gps_data": {"claimed_coords": "26.4499,80.3319", "log_coords": "26.4499,80.3319"},
                "license_plate": "UP78GH3456",
                "owner_info": "Jasneet Singh"
            }
        }
    ],
    "agriculture": [
        {
            "id": "agri_genuine",
            "name": "Genuine Crop Loss (Flood)",
            "description": "Validated crop damage with weather records matching regional flooding.",
            "data": {
                "claim_text": "Heavy rainfall and flooding destroyed 5 acres of paddy crops.",
                "image_url": "https://images.unsplash.com/photo-1500937386664-56d1dfef3854",
                "farm_geotag": "25.3176,82.9739",
                "crop_type": "Paddy",
                "claimed_loss_pct": 85,
                "sown_area": "5 Acres",
                "weather_history": {"rainfall_mm": 180.0, "event_type": "Heavy Rain"},
                "farmer_name": "Ramesh Kumar"
            }
        },
        {
            "id": "agri_weather_mismatch",
            "name": "Weather Data Mismatch (Drought Claim)",
            "description": "Farmer claims complete drought loss, but weather database records normal precipitation for the week.",
            "data": {
                "claim_text": "Severe drought and lack of rain dried up the wheat fields.",
                "image_url": "https://images.unsplash.com/photo-1500937386664-56d1dfef3854",
                "farm_geotag": "25.3176,82.9739",
                "crop_type": "Wheat",
                "claimed_loss_pct": 90,
                "sown_area": "3 Acres",
                "weather_history": {"rainfall_mm": 45.0, "event_type": "Normal precipitation"}, # Normal rain
                "farmer_name": "Suresh Singh"
            }
        },
        {
            "id": "agri_boundary_spoof",
            "name": "Field Boundary Spoofing",
            "description": "The claimed crop coordinates lie outside the registered farm boundary in government records.",
            "data": {
                "claim_text": "Hailstorm damaged mustard crop near the boundary.",
                "image_url": "https://images.unsplash.com/photo-1500937386664-56d1dfef3854",
                "farm_geotag": "28.7041,77.1025", # Mismatch coordinates
                "crop_type": "Mustard",
                "claimed_loss_pct": 50,
                "sown_area": "2.5 Acres",
                "weather_history": {"rainfall_mm": 10.0, "event_type": "Hailstorm"},
                "farmer_name": "Janvee Yadav"
            }
        }
    ],
    "media": [
        {
            "id": "media_genuine",
            "name": "Authentic Public Video",
            "description": "Genuine video clip with consistent audio, metadata, and no GAN signatures.",
            "data": {
                "claim_text": "Official press conference speech about economic policy.",
                "image_url": "https://images.unsplash.com/photo-1541872703-74c5e44368f9",
                "media_hash": "a4f89d3c2e118ba77f10b2c938de87ac6349c25ff23e618db0d312aaef7733f1",
                "audio_sync_ms": 10,
                "gan_detection_score": 0.05,
                "voice_profile_match": 0.98,
                "speaker_name": "Finance Minister"
            }
        },
        {
            "id": "media_faceswap",
            "name": "AI Face-Swap Video",
            "description": "Spliced face substitution of a political figure; exhibits lip-sync lag and GAN artifacts.",
            "data": {
                "claim_text": "Public leader making controversial comments on inflation.",
                "image_url": "https://images.unsplash.com/photo-1541872703-74c5e44368f9",
                "media_hash": "f62b77a9c33de4e8b0d2d3c9071c35ee7b49c25ff87e618db0d112aaef82c3de",
                "audio_sync_ms": 180, # Lip-sync offset!
                "gan_detection_score": 0.88, # High GAN artifacts!
                "voice_profile_match": 0.35, # Low voice match
                "speaker_name": "Opposition Leader"
            }
        },
        {
            "id": "media_voice_deepfake",
            "name": "Cloned Audio Deepfake",
            "description": "Manipulated audio track using a high-fidelity voice cloning model, flagged by spectral anomalies.",
            "data": {
                "claim_text": "Leaked audio call discussing election campaign tactics.",
                "image_url": "https://images.unsplash.com/photo-1541872703-74c5e44368f9",
                "media_hash": "c33de4e8b0d2d3c9071c35ee7b49c25ff87e618db0d112aaef82c3def62b77a9",
                "audio_sync_ms": 0,
                "gan_detection_score": 0.15,
                "voice_profile_match": 0.22, # Synthesized voice!
                "speaker_name": "Prominent Candidate"
            }
        }
    ]
}
