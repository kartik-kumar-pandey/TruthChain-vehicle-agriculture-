"use client";

import { useRef, useState, useEffect } from "react";
import FieldMapDraw from "@/components/ui/FieldMapDraw";
import { useRouter } from "next/navigation";
import { useForm, useWatch, type Resolver } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { FormField, Input, Label, Textarea } from "@/components/ui/input";
import { SectionHeader, Alert, Separator } from "@/components/ui/primitives";
import {
  Upload,
  FileImage,
  X,
  FileText,
  Activity,
  Cpu,
  CheckCircle2,
  AlertTriangle,
  Loader2,
  Zap,
  ShieldCheck,
  Blocks,
  Camera,
  MapPin,
  Compass,
  Satellite,
  Globe,
  CloudSun,
  Eye,
} from "lucide-react";
import Link from "next/link";
import { useEvaluateClaim, useEvaluateAgricultureClaim } from "@/hooks/useTruthChain";
import { cn, formatBytes } from "@/lib/utils";
import { api } from "@/lib/api";
import {
  ACCEPTED_IMAGE_TYPES,
  AGENT_ORDER,
  MAX_CLAIM_ID_LENGTH,
  MAX_DESCRIPTION_LENGTH,
  MAX_IMAGE_BYTES,
} from "@/lib/constants";
import type { ConsensusRequest } from "@/types/claim";
import { Copyable } from "@/components/ui/copyable";

const numeric: z.ZodType<number | undefined> = z.preprocess(
  (v): number | undefined => {
    if (v === "" || v === null || v === undefined) return undefined;
    const n = Number(v);
    return Number.isFinite(n) ? n : undefined;
  },
  z.number().optional(),
);

function roundFloat(val: number, decimals = 5): number {
  const factor = Math.pow(10, decimals);
  return Math.round(val * factor) / factor;
}

const createClaimSchema = z.object({
  domain: z.enum(["motor", "agriculture"]).default("motor"),
  claim_id: z
    .string()
    .trim()
    .min(1, "Claim number is required")
    .max(MAX_CLAIM_ID_LENGTH, `Claim ID too long (max ${MAX_CLAIM_ID_LENGTH})`),
  policy_number: z.string().optional(),
  vehicle_registration: z.string().optional(),
  vehicle_make_model: z.string().optional(),
  incident_date: z.string().optional(),
  incident_location: z.string().optional(),
  // Agriculture specific fields & geotagged inputs
  crop: z.string().optional(),
  field_area_hectares: numeric,
  event: z.string().optional(),
  event_date: z.string().optional(),
  location: z.string().optional(),
  claimed_loss_percent: numeric,
  latitude: numeric,
  longitude: numeric,
  field_geojson: z.string().optional(),
  image_file: z
    .custom<File | null>((val) => val === null || val instanceof File, {
      message: "Invalid image file",
    })
    .optional()
    .superRefine((val, ctx) => {
      if (!val) return;
      if (!ACCEPTED_IMAGE_TYPES.includes(val.type) &&
          !/\.(jpe?g|png|webp|bmp|tiff?)$/i.test(val.name)) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message:
            "Unsupported image type. Accepted: JPG, PNG, WEBP, BMP, TIFF.",
        });
      }
      if (val.size > MAX_IMAGE_BYTES) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: `Image too large. Maximum ${formatBytes(MAX_IMAGE_BYTES)}.`,
        });
      }
    }),
  speed: numeric,
  accel_x: numeric,
  accel_y: numeric,
  accel_z: numeric,
  speed_change: numeric,
  acceleration_change: numeric,
  gps_distance: numeric,
  gps_speed: numeric,
  description: z
    .string()
    .trim()
    .min(1, "Narrative is required")
    .max(
      MAX_DESCRIPTION_LENGTH,
      `Narrative too long (max ${MAX_DESCRIPTION_LENGTH} characters)`,
    ),
});

type CreateClaimInput = z.infer<typeof createClaimSchema>;

function readFileAsDataURL(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as string);
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

const PROCESSING_STAGES = [
  { key: "submitted", label: "Claim submitted" },
  { key: "ai_running", label: "AI consensus engine running" },
  { key: "blockchain_pending", label: "Blockchain certification pending" },
  { key: "evidence_pending", label: "Evidence verification pending" },
] as const;



export default function CreateClaimPage() {
  const router = useRouter();
  const motorMutation = useEvaluateClaim();
  const agriMutation = useEvaluateAgricultureClaim();
  const [selectedDomain, setSelectedDomain] = useState<"motor" | "agriculture">("motor");
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [imageFileLocal, setImageFileLocal] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const {
    register,
    handleSubmit,
    setValue,
    control,
    formState: { errors },
  } = useForm<CreateClaimInput>({
    resolver: zodResolver(createClaimSchema) as Resolver<CreateClaimInput>,
    defaultValues: {
      domain: "motor",
      claim_id: "",
      policy_number: "",
      vehicle_registration: "",
      vehicle_make_model: "",
      incident_date: "",
      incident_location: "",
      crop: "",
      field_area_hectares: undefined,
      event: "",
      event_date: "",
      location: "",
      claimed_loss_percent: undefined,
      image_file: null,
      speed: undefined,
      accel_x: undefined,
      accel_y: undefined,
      accel_z: undefined,
      speed_change: undefined,
      acceleration_change: undefined,
      gps_distance: undefined,
      gps_speed: undefined,
      description: "",
    },
  });

  const descriptionValue = useWatch({ control, name: "description" }) || "";
  const claimIdValue = useWatch({ control, name: "claim_id" }) || "";

  const activeMutation = selectedDomain === "agriculture" ? agriMutation : motorMutation;
  const busy = activeMutation.isPending;
  const activeError = activeMutation.error;
  const [stageIndex, setStageIndex] = useState(0);
  const startTimeRef = useRef<number | null>(null);

  useEffect(() => {
    if (!busy) {
      startTimeRef.current = null;
      return;
    }
    if (startTimeRef.current === null) {
      startTimeRef.current = Number(new Date());
    }
    const thresholds = [0, 4000, 12000, 18000];
    const update = () => {
      const start = startTimeRef.current ?? Number(new Date());
      const now = Number(new Date());
      const e = now - start;
      let idx = 0;
      for (let i = thresholds.length - 1; i >= 0; i--) {
        if (e >= thresholds[i]) {
          idx = i;
          break;
        }
      }
      setStageIndex(idx);
    };
    const id0 = window.setTimeout(update, 0);
    const id = window.setInterval(update, 1000);
    return () => {
      window.clearTimeout(id0);
      window.clearInterval(id);
    };
  }, [busy]);

  const processingStageIndex = busy ? stageIndex : -1;

  const onFilePicked = async (files: FileList | null) => {
    const f = files?.[0] ?? null;
    if (!f) {
      setImageFileLocal(null);
      setImagePreview(null);
      setValue("image_file", null, { shouldValidate: true });
      return;
    }
    setImageFileLocal(f);
    setValue("image_file", f, { shouldValidate: true });
    try {
      const dataUrl = await readFileAsDataURL(f);
      setImagePreview(dataUrl);
    } catch {
      setImagePreview(null);
    }
  };

  const removeImage = () => {
    setImageFileLocal(null);
    setImagePreview(null);
    setValue("image_file", null, { shouldValidate: true });
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const [isCameraActive, setIsCameraActive] = useState(false);
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);

  // Field Polygon Canvas Drawing state
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [polygonPoints, setPolygonPoints] = useState<{ x: number; y: number }[]>([]);

  // Sentinel-2 Satellite Preview state
  const [satPreview, setSatPreview] = useState<{
    status: string;
    scenes_found: number;
    best_scene?: {
      scene_id: string;
      datetime: string | null;
      cloud_cover: number | null;
      collection: string;
    };
    tile_url?: string;
    cdse_wms_url?: string;
    message?: string;
  } | null>(null);
  const [satLoading, setSatLoading] = useState(false);
  const [fieldConfirmed, setFieldConfirmed] = useState(false);

  const startCamera = async () => {
    try {
      setIsCameraActive(true);
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "environment" },
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
      }

      // Fetch live GPS coordinates if available
      if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition((pos) => {
          setValue("latitude", pos.coords.latitude);
          setValue("longitude", pos.coords.longitude);
        });
      }
    } catch (err) {
      console.error("Camera access failed:", err);
      setIsCameraActive(false);
    }
  };

  const capturePhoto = () => {
    if (!videoRef.current) return;
    const canvas = document.createElement("canvas");
    canvas.width = videoRef.current.videoWidth || 640;
    canvas.height = videoRef.current.videoHeight || 480;
    const ctx = canvas.getContext("2d");
    if (ctx) {
      ctx.drawImage(videoRef.current, 0, 0, canvas.width, canvas.height);
      const dataUrl = canvas.toDataURL("image/jpeg");
      setImagePreview(dataUrl);

      // Convert data URL to File object
      fetch(dataUrl)
        .then((res) => res.blob())
        .then((blob) => {
          const file = new File([blob], "geotagged_crop_field.jpg", { type: "image/jpeg" });
          setImageFileLocal(file);
          setValue("image_file", file, { shouldValidate: true });
        });
    }
    stopCamera();
  };

  const stopCamera = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    setIsCameraActive(false);
  };

  const latVal = useWatch({ control, name: "latitude" }) ?? 26.3155;
  const lngVal = useWatch({ control, name: "longitude" }) ?? 80.1255;

  // Draw Live ESRI Satellite Tile, Plot Boundary, and Vertices on Canvas
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    // Convert Lat/Lng to Esri World Imagery Bounding Box for true location satellite imagery
    const delta = 0.003;
    const minLng = lngVal - delta;
    const maxLng = lngVal + delta;
    const minLat = latVal - delta;
    const maxLat = latVal + delta;
    const bboxStr = `${minLng},${minLat},${maxLng},${maxLat}`;

    // Live High-Resolution ESRI World Imagery Satellite REST API URL
    const esriSatUrl = `https://services.arcgisonline.com/arcgis/rest/services/World_Imagery/MapServer/export?bbox=${bboxStr}&bboxSR=4326&imageSR=4326&size=${canvas.width},${canvas.height}&format=jpg&f=image`;

    const satImg = new Image();
    satImg.crossOrigin = "anonymous";
    satImg.src = esriSatUrl;

    const drawOverlay = () => {
      // Draw Grid Lines (Satellite Map feel)
      ctx.strokeStyle = "rgba(255, 255, 255, 0.2)";
      ctx.lineWidth = 1;
      for (let x = 0; x < canvas.width; x += 40) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, canvas.height);
        ctx.stroke();
      }
      for (let y = 0; y < canvas.height; y += 40) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(canvas.width, y);
        ctx.stroke();
      }

      if (polygonPoints.length === 0) return;

      // Draw Polygon Outline & Fill
      ctx.beginPath();
      ctx.moveTo(polygonPoints[0].x, polygonPoints[0].y);
      for (let i = 1; i < polygonPoints.length; i++) {
        ctx.lineTo(polygonPoints[i].x, polygonPoints[i].y);
      }
      if (polygonPoints.length >= 3) {
        ctx.closePath();
        ctx.fillStyle = "rgba(16, 185, 129, 0.35)";
        ctx.fill();
      }

      ctx.strokeStyle = "#10b981";
      ctx.lineWidth = 2.5;
      ctx.stroke();

      // Draw Vertex Points
      for (let i = 0; i < polygonPoints.length; i++) {
        ctx.beginPath();
        ctx.arc(polygonPoints[i].x, polygonPoints[i].y, 5, 0, 2 * Math.PI);
        ctx.fillStyle = i === 0 ? "#38bdf8" : "#34d399";
        ctx.fill();
        ctx.strokeStyle = "#ffffff";
        ctx.lineWidth = 1.5;
        ctx.stroke();
      }
    };

    satImg.onload = () => {
      ctx.drawImage(satImg, 0, 0, canvas.width, canvas.height);
      drawOverlay();
    };

    satImg.onerror = () => {
      // Fallback dark background if offline
      ctx.fillStyle = "#020617";
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      drawOverlay();
    };
  }, [polygonPoints, selectedDomain, latVal, lngVal]);

  const handleCanvasClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) return;
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    const newPoints = [...polygonPoints, { x, y }];
    setPolygonPoints(newPoints);

    // Calculate approximate area in hectares from polygon coordinates
    if (newPoints.length >= 3) {
      const baseLat = latVal;
      const baseLng = lngVal;
      const canvasW = canvasRef.current?.width || 380;
      const canvasH = canvasRef.current?.height || 180;
      // Map pixel coords to geographic coords based on the visible tile extent
      const delta = 0.003;
      const geoCoords = newPoints.map((p) => [
        roundFloat(baseLng - delta + (p.x / canvasW) * (2 * delta), 6),
        roundFloat(baseLat + delta - (p.y / canvasH) * (2 * delta), 6),
      ]);
      geoCoords.push(geoCoords[0]); // Close polygon loop

      const geoJsonStr = JSON.stringify({
        type: "Polygon",
        coordinates: [geoCoords],
      });
      setValue("field_geojson", geoJsonStr);

      // Simple Shoelace formula for polygon area estimation in hectares
      let areaSum = 0;
      for (let i = 0; i < newPoints.length; i++) {
        const j = (i + 1) % newPoints.length;
        areaSum += newPoints[i].x * newPoints[j].y;
        areaSum -= newPoints[j].x * newPoints[i].y;
      }
      const pixelArea = Math.abs(areaSum) / 2;
      // Convert pixel area to hectares (~0.05 ha per 1000 px^2)
      const calculatedHectares = roundFloat(Math.max(0.5, (pixelArea / 1000) * 0.45), 2);
      setValue("field_area_hectares", calculatedHectares);
    }
  };

  const clearCanvasPolygon = () => {
    setPolygonPoints([]);
    setValue("field_geojson", "");
    setValue("field_area_hectares", undefined);
    setSatPreview(null);
    setFieldConfirmed(false);
  };

  const fetchSatellitePreview = async () => {
    if (polygonPoints.length < 3) return;

    const geoJsonStr = control._formValues.field_geojson;
    if (!geoJsonStr) return;

    let geojson: Record<string, unknown>;
    try {
      geojson = JSON.parse(geoJsonStr as string);
    } catch {
      return;
    }

    // Use event_date or default to recent range
    const eventDate = control._formValues.event_date || "17 September 2026";
    // Parse various date formats into YYYY-MM-DD
    let endDate = "2026-09-17";
    try {
      const d = new Date(eventDate);
      if (!isNaN(d.getTime())) {
        endDate = d.toISOString().split("T")[0];
      }
    } catch { /* use default */ }

    // Start date: 30 days before end
    const startD = new Date(endDate);
    startD.setDate(startD.getDate() - 30);
    const startDate = startD.toISOString().split("T")[0];

    setSatLoading(true);
    setFieldConfirmed(true);

    try {
      const result = await api.satellitePreview({
        field_geojson: geojson,
        start_date: startDate,
        end_date: endDate,
        max_cloud: 20,
      });
      setSatPreview(result);
    } catch (err) {
      console.error("Satellite preview failed:", err);
      setSatPreview({
        status: "error",
        scenes_found: 0,
        message: String(err),
      });
    } finally {
      setSatLoading(false);
    }
  };

  const onSubmit = handleSubmit(async (values) => {
    if (selectedDomain === "agriculture") {
      // Extract centroid from drawn polygon for lat/lng if not manually set
      let finalLat = values.latitude;
      let finalLng = values.longitude;
      let fieldGeoJSON: Record<string, unknown> | null = null;

      if (values.field_geojson) {
        try {
          fieldGeoJSON = JSON.parse(values.field_geojson);
          // Compute centroid from polygon coordinates if lat/lng not explicitly set
          if (!finalLat || !finalLng) {
            const coords = (fieldGeoJSON as { coordinates: number[][][] }).coordinates[0];
            const sumLng = coords.slice(0, -1).reduce((s, c) => s + c[0], 0);
            const sumLat = coords.slice(0, -1).reduce((s, c) => s + c[1], 0);
            const count = coords.length - 1;
            finalLng = parseFloat((sumLng / count).toFixed(6));
            finalLat = parseFloat((sumLat / count).toFixed(6));
          }
        } catch { /* ignore parse error */ }
      }

      const agriPayload: Record<string, unknown> = {
        claim_id: values.claim_id,
        domain: "agriculture",
        crop: values.crop || "Wheat",
        field_area_hectares: values.field_area_hectares || 2.0,
        event: values.event || "Heavy rain",
        event_date: values.event_date || "",
        location: values.location || "",
        claimed_loss_percent: values.claimed_loss_percent || 0,
        claim_text: values.description,
        latitude: finalLat ?? 26.8467,
        longitude: finalLng ?? 80.9462,
        field_geojson: fieldGeoJSON ?? {
          type: "Polygon",
          coordinates: [[[80.9460, 26.8465], [80.9468, 26.8465], [80.9468, 26.8472], [80.9460, 26.8472], [80.9460, 26.8465]]]
        }
      };

      if (values.image_file) {
        try {
          const dataUrl = await readFileAsDataURL(values.image_file);
          agriPayload.image = dataUrl;
          agriPayload.image_metadata = {
            latitude: finalLat ?? 26.8467,
            longitude: finalLng ?? 80.9462,
            timestamp: values.event_date || new Date().toISOString().split("T")[0],
          };
        } catch {
          // ignore
        }
      }

      console.log("TruthChain Agriculture request:", agriPayload);
      try {
        const result = await agriMutation.mutateAsync(agriPayload);
        console.log("TruthChain Agriculture response:", result);
        router.push(`/claims/${encodeURIComponent(values.claim_id)}`);
      } catch (err) {
        console.error("TruthChain Agriculture API error:", err);
      }
    } else {
      const metadata: Record<string, unknown> = {};
      if (values.policy_number) metadata.policy_number = values.policy_number;
      if (values.vehicle_registration)
        metadata.vehicle_registration = values.vehicle_registration;
      if (values.vehicle_make_model)
        metadata.vehicle_make_model = values.vehicle_make_model;
      if (values.incident_date) metadata.incident_date = values.incident_date;
      if (values.incident_location)
        metadata.incident_location = values.incident_location;

      const sensor: Record<string, number> = {};
      if (values.speed !== undefined && values.speed !== null)
        sensor.speed = values.speed;
      if (values.accel_x !== undefined && values.accel_x !== null)
        sensor.accel_x = values.accel_x;
      if (values.accel_y !== undefined && values.accel_y !== null)
        sensor.accel_y = values.accel_y;
      if (values.accel_z !== undefined && values.accel_z !== null)
        sensor.accel_z = values.accel_z;

      if (Object.keys(sensor).length > 0) {
        metadata.sensor = sensor;
        metadata.sensor_data = sensor;
      }

      if (values.image_file) {
        try {
          const dataUrl = await readFileAsDataURL(values.image_file);
          metadata.image = dataUrl;
        } catch {
          // ignore
        }
      }

      const payload: ConsensusRequest = {
        claim_id: values.claim_id,
        description: values.description,
        metadata,
      };

      console.log("TruthChain Motor API request (evaluate):", payload);
      try {
        const result = await motorMutation.mutateAsync(payload);
        console.log("TruthChain Motor API response:", result);
        router.push(`/claims/${encodeURIComponent(values.claim_id)}`);
      } catch (err) {
        console.error("TruthChain Motor API error:", err);
      }
    }
  });

  return (
    <div className="space-y-6">
      <SectionHeader
        eyebrow="Claim Submission"
        title="Create & Evaluate Insurance Claim"
        description="Submit claim narrative, telemetry, and damage photos to the TruthChain 8-Agent AI Consensus Engine and Sepolia blockchain. The result is generated by the real backend API."
        actions={
          <Badge variant="info" className="font-mono text-[10px]">
            POST /api/v1/consensus/evaluate
          </Badge>
        }
      />

      {activeError && (
        <Alert variant="danger">
          <div className="flex items-start gap-2">
            <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" />
            <div>
              <div className="font-medium">Evaluation failed</div>
              <div className="text-xs mt-0.5 opacity-90">
                {activeError.message || String(activeError)}
              </div>
            </div>
          </div>
        </Alert>
      )}

      <form onSubmit={onSubmit} className="space-y-6" noValidate>
        <Card className="border-cyan-900/40 bg-slate-900/60">
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-base">
              <Blocks className="h-4 w-4 text-cyan-400" />
              Select Insurance Domain
            </CardTitle>
            <CardDescription className="text-xs">
              Choose the evaluation pipeline and model architecture for this claim.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => {
                  setSelectedDomain("motor");
                  setValue("domain", "motor");
                  // Clear agriculture-specific fields when switching to motor
                  setValue("crop", "");
                  setValue("field_area_hectares", undefined);
                  setValue("event", "");
                  setValue("event_date", "");
                  setValue("location", "");
                  setValue("claimed_loss_percent", undefined);
                  setValue("latitude", undefined);
                  setValue("longitude", undefined);
                  setValue("field_geojson", "");
                  setPolygonPoints([]);
                  setSatPreview(null);
                  setFieldConfirmed(false);
                }}
                className={cn(
                  "flex flex-col items-start p-4 rounded-xl border text-left transition-all",
                  selectedDomain === "motor"
                    ? "border-cyan-500 bg-cyan-950/30 text-slate-100 shadow-lg shadow-cyan-950/50"
                    : "border-slate-800 bg-slate-950/30 text-slate-400 hover:border-slate-700 hover:text-slate-200"
                )}
              >
                <div className="flex items-center gap-2 font-semibold text-sm">
                  <span>🚗 Motor Insurance</span>
                  {selectedDomain === "motor" && (
                    <Badge variant="info" className="text-[10px]">Active</Badge>
                  )}
                </div>
                <div className="text-xs text-slate-400 mt-1">
                  8-Agent Consensus: ResNet-50 Vision, Telemetry, Narrative & Sepolia Proof.
                </div>
              </button>

              <button
                type="button"
                onClick={() => {
                  setSelectedDomain("agriculture");
                  setValue("domain", "agriculture");
                  // Clear motor-specific fields when switching to agriculture
                  setValue("policy_number", "");
                  setValue("vehicle_registration", "");
                  setValue("vehicle_make_model", "");
                  setValue("incident_date", "");
                  setValue("incident_location", "");
                  setValue("speed", undefined);
                  setValue("accel_x", undefined);
                  setValue("accel_y", undefined);
                  setValue("accel_z", undefined);
                }}
                className={cn(
                  "flex flex-col items-start p-4 rounded-xl border text-left transition-all",
                  selectedDomain === "agriculture"
                    ? "border-emerald-500 bg-emerald-950/30 text-slate-100 shadow-lg shadow-emerald-950/50"
                    : "border-slate-800 bg-slate-950/30 text-slate-400 hover:border-slate-700 hover:text-slate-200"
                )}
              >
                <div className="flex items-center gap-2 font-semibold text-sm">
                  <span>🌾 Agriculture Insurance</span>
                  {selectedDomain === "agriculture" && (
                    <Badge variant="success" className="text-[10px]">Active</Badge>
                  )}
                </div>
                <div className="text-xs text-slate-400 mt-1">
                  Parallel Pipeline: Satellite Index, Crop Imagery, Weather & Risk Engine.
                </div>
              </button>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FileText className="h-4 w-4 text-cyan-400" />
              Claim & Vehicle Information
            </CardTitle>
            <CardDescription>
              Administrative identifiers and incident context.
            </CardDescription>
          </CardHeader>
          <CardContent className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <FormField
              label="Claim Number"
              required
              error={errors.claim_id?.message}
              hint={`${claimIdValue.length}/${MAX_CLAIM_ID_LENGTH}`}
            >
              <Input
                placeholder={selectedDomain === "agriculture" ? "AGRI-2026-001" : "TC-FRONTEND-E2E-001"}
                {...register("claim_id")}
              />
            </FormField>

            {selectedDomain === "agriculture" ? (
              <>
                <FormField label="Crop Type" required error={errors.crop?.message}>
                  <Input placeholder="e.g. Wheat, Rice, Corn" {...register("crop")} />
                </FormField>
                <FormField label="Field Area (Hectares)" required error={errors.field_area_hectares?.message} hint="Auto-calculated from drawn field polygon">
                  <Input type="number" step="any" placeholder="Auto-calculated (e.g. 2.03)" {...register("field_area_hectares")} />
                </FormField>
                <FormField label="Peril / Weather Event" required error={errors.event?.message}>
                  <Input placeholder="e.g. Heavy rain, Flood, Hailstorm" {...register("event")} />
                </FormField>
                <FormField label="Event Date" required error={errors.event_date?.message}>
                  <Input placeholder="e.g. 17 September 2026" {...register("event_date")} />
                </FormField>
                <FormField label="Location / Village" required error={errors.location?.message}>
                  <Input placeholder="Village Rampur, District Lucknow" {...register("location")} />
                </FormField>
                <FormField label="Claimed Loss (%)" required error={errors.claimed_loss_percent?.message}>
                  <Input type="number" step="any" placeholder="65.0" {...register("claimed_loss_percent")} />
                </FormField>
                <FormField label="Photo GPS Latitude (°N)" error={errors.latitude?.message}>
                  <Input type="number" step="any" placeholder="26.8467" {...register("latitude")} />
                </FormField>
                <FormField label="Photo GPS Longitude (°E)" error={errors.longitude?.message}>
                  <Input type="number" step="any" placeholder="80.9462" {...register("longitude")} />
                </FormField>
                <div className="col-span-1 md:col-span-2 space-y-2">
                  <div className="flex items-center justify-between">
                    <Label className="flex items-center gap-1.5 text-xs font-semibold text-emerald-400">
                      <Compass className="h-4 w-4" />
                      Field Boundary Map — Draw your field polygon on the satellite map
                    </Label>
                    <Button type="button" variant="outline" size="sm" onClick={clearCanvasPolygon} className="h-6 text-[11px] text-slate-400">
                      Clear Field
                    </Button>
                  </div>

                  {/* Real Leaflet Satellite Map with Draw Tool */}
                  <FieldMapDraw
                    center={[latVal ?? 26.8467, lngVal ?? 80.9462]}
                    onPolygonChange={(geojson, hectares) => {
                      if (geojson) {
                        setValue("field_geojson", JSON.stringify(geojson));
                        setValue("field_area_hectares", hectares);
                        setPolygonPoints([{ x: 0, y: 0 }]); // mark as having polygon
                      } else {
                        setValue("field_geojson", "");
                        setValue("field_area_hectares", undefined);
                        setPolygonPoints([]);
                      }
                      setSatPreview(null);
                      setFieldConfirmed(false);
                    }}
                    onLocationDetected={({ locationStr, lat, lng }) => {
                      setValue("location", locationStr);
                      setValue("latitude", parseFloat(lat.toFixed(6)));
                      setValue("longitude", parseFloat(lng.toFixed(6)));
                    }}
                  />

                  <div className="text-[11px] text-slate-400 font-mono flex items-center gap-2 px-1">
                    {polygonPoints.length === 0
                      ? "✏️ Use the polygon draw tool (pentagon icon) on the map to outline your farm boundary"
                      : `✓ Field polygon drawn · Area auto-calculated from coordinates`}
                  </div>

                  {/* Confirm Field & Fetch Sentinel-2 Preview */}
                  {polygonPoints.length >= 1 && !fieldConfirmed && (
                    <Button
                      type="button"
                      size="sm"
                      onClick={fetchSatellitePreview}
                      disabled={satLoading}
                      className="mt-2 bg-emerald-600 hover:bg-emerald-500 text-white text-xs"
                    >
                      {satLoading ? (
                        <><Loader2 className="h-3.5 w-3.5 animate-spin mr-1" /> Searching Sentinel-2…</>
                      ) : (
                        <><Satellite className="h-3.5 w-3.5 mr-1" /> Confirm Field & Fetch Satellite Imagery</>
                      )}
                    </Button>
                  )}


                  {/* ── Sentinel-2 Satellite Preview Panel ── */}
                  {satLoading && (
                    <div className="mt-3 p-4 rounded-xl border border-cyan-900/50 bg-gradient-to-br from-slate-950 to-cyan-950/20">
                      <div className="flex items-center gap-3 text-sm text-cyan-300">
                        <Loader2 className="h-5 w-5 animate-spin text-cyan-400" />
                        <div>
                          <div className="font-semibold">Searching Sentinel-2 imagery…</div>
                          <div className="text-[11px] text-slate-400 font-mono mt-0.5">Querying CDSE STAC API → Copernicus Data Space</div>
                        </div>
                      </div>
                    </div>
                  )}

                  {satPreview && !satLoading && (
                    <div className="mt-3 rounded-xl border border-emerald-800/60 bg-gradient-to-br from-slate-950 via-emerald-950/10 to-slate-950 overflow-hidden">
                      {/* Header */}
                      <div className="flex items-center justify-between px-4 py-2.5 border-b border-emerald-900/40 bg-emerald-950/30">
                        <div className="flex items-center gap-2">
                          <Satellite className="h-4 w-4 text-emerald-400" />
                          <span className="text-xs font-bold text-emerald-300 tracking-wide uppercase">Sentinel-2 Satellite Evidence</span>
                        </div>
                        <Badge
                          variant={satPreview.status === "success" ? "success" : satPreview.status === "fallback" ? "warning" : "info"}
                          className="text-[10px] font-mono"
                        >
                          {satPreview.status === "success" ? "✓ CDSE" : satPreview.status === "fallback" ? "ESRI Fallback" : satPreview.status === "no_scenes" ? "No Scenes" : "Error"}
                        </Badge>
                      </div>

                      {/* Satellite Image */}
                      {satPreview.tile_url && (
                        <div className="relative">
                          {/* eslint-disable-next-line @next/next/no-img-element */}
                          <img
                            src={satPreview.tile_url}
                            alt="Sentinel-2 satellite view of field"
                            className="w-full h-48 object-cover"
                            crossOrigin="anonymous"
                          />
                          <div className="absolute top-2 left-2 bg-black/70 backdrop-blur-sm rounded-lg px-2 py-1 flex items-center gap-1.5">
                            <Globe className="h-3 w-3 text-cyan-400" />
                            <span className="text-[10px] text-white font-mono">10m Resolution</span>
                          </div>
                          <div className="absolute bottom-2 right-2 bg-black/70 backdrop-blur-sm rounded-lg px-2 py-1">
                            <span className="text-[10px] text-emerald-300 font-mono">🛰 Sentinel-2 L2A</span>
                          </div>
                        </div>
                      )}

                      {/* Scene Metadata */}
                      {satPreview.best_scene && (
                        <div className="px-4 py-3 space-y-2">
                          <div className="grid grid-cols-3 gap-3">
                            <div className="text-center p-2 rounded-lg bg-slate-900/60 border border-slate-800">
                              <Eye className="h-3.5 w-3.5 text-cyan-400 mx-auto mb-1" />
                              <div className="text-[10px] text-slate-400">Scene Date</div>
                              <div className="text-xs font-bold text-slate-200">
                                {satPreview.best_scene.datetime
                                  ? new Date(satPreview.best_scene.datetime).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" })
                                  : "—"}
                              </div>
                            </div>
                            <div className="text-center p-2 rounded-lg bg-slate-900/60 border border-slate-800">
                              <CloudSun className="h-3.5 w-3.5 text-amber-400 mx-auto mb-1" />
                              <div className="text-[10px] text-slate-400">Cloud Cover</div>
                              <div className="text-xs font-bold text-slate-200">
                                {satPreview.best_scene.cloud_cover != null
                                  ? `${satPreview.best_scene.cloud_cover.toFixed(1)}%`
                                  : "—"}
                              </div>
                            </div>
                            <div className="text-center p-2 rounded-lg bg-slate-900/60 border border-slate-800">
                              <Satellite className="h-3.5 w-3.5 text-emerald-400 mx-auto mb-1" />
                              <div className="text-[10px] text-slate-400">Scenes Found</div>
                              <div className="text-xs font-bold text-slate-200">
                                {satPreview.scenes_found}
                              </div>
                            </div>
                          </div>
                          <div className="text-[10px] text-slate-500 font-mono truncate">
                            Scene: {satPreview.best_scene.scene_id}
                          </div>
                        </div>
                      )}

                      {/* No scenes / error message */}
                      {!satPreview.best_scene && satPreview.message && (
                        <div className="px-4 py-3">
                          <div className="text-xs text-slate-400">{satPreview.message}</div>
                        </div>
                      )}

                      {/* Architecture badge */}
                      <div className="px-4 py-2 border-t border-emerald-900/30 bg-emerald-950/20">
                        <div className="flex items-center justify-between text-[10px] text-slate-500 font-mono">
                          <span>Farmer Polygon → CDSE STAC → Sentinel-2 → Preview</span>
                          <span>Same data → SatelliteAgent AI</span>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </>
            ) : (
              <>
                <FormField label="Policy Number" required error={errors.policy_number?.message}>
                  <Input placeholder="POL-2026-008421" {...register("policy_number")} />
                </FormField>
                <FormField label="Vehicle Registration (VIN/Reg)" required error={errors.vehicle_registration?.message}>
                  <Input placeholder="VIN or license plate" {...register("vehicle_registration")} />
                </FormField>
                <FormField label="Vehicle Make & Model" error={errors.vehicle_make_model?.message}>
                  <Input placeholder="e.g. Toyota Camry 2022" {...register("vehicle_make_model")} />
                </FormField>
                <FormField label="Incident Date" error={errors.incident_date?.message}>
                  <Input type="date" {...register("incident_date")} />
                </FormField>
                <FormField label="Incident Location" error={errors.incident_location?.message}>
                  <Input placeholder="Intersection / GPS coordinates / address" {...register("incident_location")} />
                </FormField>
              </>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FileImage className="h-4 w-4 text-cyan-400" />
              Visual Evidence
            </CardTitle>
            <CardDescription>
              Upload vehicle damage photo. Accepted: JPG, PNG, WEBP, BMP, TIFF.
              Max 10 MiB.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <input
              id="damage-image-upload"
              ref={fileInputRef}
              type="file"
              accept={ACCEPTED_IMAGE_TYPES.join(",")}
              className="hidden"
              onChange={(e) => onFilePicked(e.target.files)}
            />
            {isCameraActive ? (
              <div className="flex flex-col items-center gap-3 p-4 rounded-xl border border-cyan-500 bg-slate-950">
                <video ref={videoRef} autoPlay playsInline className="max-h-64 w-full rounded-lg object-cover bg-black" />
                <div className="flex gap-2">
                  <Button type="button" variant="default" size="sm" onClick={capturePhoto} className="bg-emerald-600 hover:bg-emerald-500">
                    <Camera className="h-4 w-4 mr-1.5" /> Snap Geotagged Photo
                  </Button>
                  <Button type="button" variant="outline" size="sm" onClick={stopCamera}>
                    Cancel Camera
                  </Button>
                </div>
              </div>
            ) : !imagePreview ? (
              <div className="space-y-3">
                <div className="flex justify-end">
                  <Button type="button" variant="outline" size="sm" onClick={startCamera} className="text-xs text-cyan-400 border-cyan-900 hover:bg-cyan-950">
                    <Camera className="h-3.5 w-3.5 mr-1" /> Open Live Geotag Camera
                  </Button>
                </div>
                <label
                htmlFor="damage-image-upload"
                onClick={() => fileInputRef.current?.click()}
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => {
                  e.preventDefault();
                  if (e.dataTransfer?.files?.length) {
                    onFilePicked(e.dataTransfer.files);
                  }
                }}
                className={cn(
                  "block rounded-xl border-2 border-dashed cursor-pointer transition-colors",
                  errors.image_file
                    ? "border-red-700 bg-red-950/20"
                    : "border-slate-700 hover:border-cyan-600/60 bg-slate-900/30 hover:bg-slate-900/50",
                )}
              >
                <div className="flex flex-col items-center justify-center py-12 px-6 text-center gap-3">
                  <div className="h-12 w-12 rounded-xl bg-slate-800 flex items-center justify-center text-slate-400">
                    <Upload className="h-5 w-5" />
                  </div>
                  <div>
                    <div className="text-sm font-medium text-slate-200">
                      Drag & drop damage photo, or click to browse
                    </div>
                    <div className="text-xs text-slate-500 mt-1">
                      JPG, PNG, WEBP, BMP, TIFF · up to 10 MiB
                    </div>
                  </div>
                </div>
              </label>
              </div>
            ) : (
              <div className="rounded-xl border border-slate-800 overflow-hidden bg-slate-900/30">
                <div className="flex flex-col md:flex-row">
                  <div className="md:w-1/2 bg-black/30 flex items-center justify-center p-4">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={imagePreview}
                      alt="Damage preview"
                      className="max-h-60 max-w-full object-contain rounded-lg"
                    />
                  </div>
                  <div className="md:w-1/2 p-5 space-y-3 flex flex-col justify-between">
                    <div className="space-y-2">
                      <div className="flex items-center justify-between gap-3">
                        <Label>Uploaded image</Label>
                        <Badge variant="success" className="font-mono">
                          Valid
                        </Badge>
                      </div>
                      <div className="text-sm text-slate-200 break-all">
                        {imageFileLocal?.name || "uploaded-image"}
                      </div>
                      <div className="text-xs text-slate-500 font-mono">
                        {imageFileLocal
                          ? `${formatBytes(imageFileLocal.size)} · ${imageFileLocal.type || "unknown type"}`
                          : ""}
                      </div>
                    </div>
                    <div className="flex gap-2">
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => fileInputRef.current?.click()}
                      >
                        Replace
                      </Button>
                      <Button
                        type="button"
                        variant="destructive"
                        size="sm"
                        onClick={removeImage}
                      >
                        <X className="h-3.5 w-3.5" />
                        Remove
                      </Button>
                    </div>
                  </div>
                </div>
              </div>
            )}
            {errors.image_file && (
              <p className="mt-2 text-xs text-rose-400">
                {errors.image_file.message}
              </p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Activity className="h-4 w-4 text-cyan-400" />
              Sensor Telemetry
            </CardTitle>
            <CardDescription>
              USER TELEMETRY · Raw readings passed to SensorAgent. Leave fields
              blank if not measured.
            </CardDescription>
          </CardHeader>
          <CardContent className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <FormField
              label="Speed (km/h)"
              error={errors.speed?.message}
            >
              <Input
                type="number"
                step="any"
                placeholder="38.0"
                {...register("speed")}
              />
            </FormField>
            <FormField
              label="Accel X (g)"
              error={errors.accel_x?.message}
            >
              <Input
                type="number"
                step="any"
                placeholder="2.0"
                {...register("accel_x")}
              />
            </FormField>
            <FormField
              label="Accel Y (g)"
              error={errors.accel_y?.message}
            >
              <Input
                type="number"
                step="any"
                placeholder="3.0"
                {...register("accel_y")}
              />
            </FormField>
            <FormField
              label="Accel Z (g)"
              error={errors.accel_z?.message}
            >
              <Input
                type="number"
                step="any"
                placeholder="9.2"
                {...register("accel_z")}
              />
            </FormField>
            <FormField
              label="Speed Change"
              error={errors.speed_change?.message}
            >
              <Input
                type="number"
                step="any"
                placeholder="4.0"
                {...register("speed_change")}
              />
            </FormField>
            <FormField
              label="Accel Change"
              error={errors.acceleration_change?.message}
            >
              <Input
                type="number"
                step="any"
                placeholder="1.5"
                {...register("acceleration_change")}
              />
            </FormField>
            <FormField
              label="GPS Distance (m)"
              error={errors.gps_distance?.message}
            >
              <Input
                type="number"
                step="any"
                placeholder="42.86"
                {...register("gps_distance")}
              />
            </FormField>
            <FormField
              label="GPS Speed"
              error={errors.gps_speed?.message}
            >
              <Input
                type="number"
                step="any"
                placeholder="42.86"
                {...register("gps_speed")}
              />
            </FormField>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Cpu className="h-4 w-4 text-cyan-400" />
              Claimant Narrative
            </CardTitle>
            <CardDescription>
              The plain-language incident description consumed by TextAgent and
              CrossModalAgent.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <FormField
              label="Incident narrative"
              required
              error={errors.description?.message}
              hint={`${descriptionValue.length}/${MAX_DESCRIPTION_LENGTH} characters`}
            >
              <Textarea
                rows={7}
                placeholder="Describe the incident, location of damage, circumstances, etc. Example: My vehicle was involved in a front-right collision. The front fender and bumper are heavily dented and scratched, and the front lamp area is damaged."
                {...register("description")}
              />
            </FormField>
          </CardContent>
        </Card>

        <Card className="border-cyan-900/50 bg-cyan-950/10">
          <CardContent className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 py-5">
            <div className="space-y-1.5">
              <div className="flex items-center gap-2">
                <Zap className="h-4 w-4 text-cyan-400" />
                <div className="text-sm font-semibold text-slate-100">
                  Evaluate Claim
                </div>
              </div>
              <div className="text-xs text-slate-400 max-w-xl">
                Triggers the real TruthChain AI consensus pipeline on{" "}
                <span className="font-mono">127.0.0.1:8000</span>. The Python
                terminal will show per-agent pipeline logs.
              </div>
              <div className="text-[11px] text-slate-500 font-mono flex flex-wrap items-center gap-1.5 mt-1">
                {AGENT_ORDER.map((name, i) => (
                  <span key={name} className="inline-flex items-center gap-1">
                    <Badge variant="info" className="font-mono text-[10px]">
                      {i + 1}. {name}
                    </Badge>
                    {i < AGENT_ORDER.length - 1 && (
                      <span className="text-slate-600">→</span>
                    )}
                  </span>
                ))}
                <span className="text-slate-600">→</span>
                <Badge variant="blockchain" className="font-mono text-[10px]">
                  BlockchainCertificate
                </Badge>
              </div>
            </div>
            <div className="shrink-0 flex items-center gap-3">
              <Link href="/claims">
                <Button type="button" variant="outline">
                  Cancel
                </Button>
              </Link>
              <Button
                type="submit"
                size="lg"
                disabled={busy}
                className="min-w-[190px]"
              >
                {busy ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Evaluating…
                  </>
                ) : (
                  <>
                    <ShieldCheck className="h-4 w-4" />
                    Evaluate Claim
                  </>
                )}
              </Button>
            </div>
          </CardContent>
        </Card>

        {busy && (
          <Card className="border-cyan-800/60 bg-slate-900/60">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Loader2 className="h-4 w-4 animate-spin text-cyan-400" />
                TRUTHCHAIN AI CONSENSUS
              </CardTitle>
              <CardDescription>
                Pipeline running… This can take 10–30 seconds depending on
                upstream providers.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-4 space-y-3">
                {PROCESSING_STAGES.map((s, i) => {
                  const active = i === processingStageIndex;
                  const done = i < processingStageIndex;
                  return (
                    <div
                      key={s.key}
                      className={cn(
                        "flex items-center gap-3 text-sm",
                      )}
                    >
                      <span
                        className={cn(
                          "h-2.5 w-2.5 rounded-full shrink-0",
                          done
                            ? "bg-emerald-400"
                            : active
                              ? "bg-cyan-400 agent-pulse"
                              : "bg-slate-700",
                        )}
                      />
                      <span
                        className={cn(
                          done
                            ? "text-slate-300"
                            : active
                              ? "text-cyan-300 font-medium"
                              : "text-slate-500",
                        )}
                      >
                        {s.label}
                      </span>
                      {done && (
                        <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400 ml-auto" />
                      )}
                    </div>
                  );
                })}
              </div>
              <Separator />
              <div className="flex items-center justify-between text-[11px] text-slate-500">
                <div className="flex items-center gap-1.5">
                  <Blocks className="h-3.5 w-3.5 text-purple-400" />
                  Awaiting Sepolia AssessmentRegistry certificate
                </div>
                <div className="font-mono">
                  {typeof claimIdValue === "string" || typeof claimIdValue === "number"
                    ? String(claimIdValue)
                    : "preparing claim…"}
                </div>
                {Boolean((activeMutation.variables as Record<string, unknown> | undefined)?.claim_id) && (
                  <Copyable
                    value={String((activeMutation.variables as Record<string, unknown>).claim_id)}
                    truncate={false}
                    className="hidden"
                  />
                )}
              </div>
            </CardContent>
          </Card>
        )}
      </form>
    </div>
  );
}
