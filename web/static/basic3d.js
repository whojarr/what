import * as THREE from "three";

let active = null;

const CAVE_OVERLAP = 0.12;

function vec3(arr, fallback = [0, 0, 0]) {
  const src = Array.isArray(arr) ? arr : fallback;
  return new THREE.Vector3(Number(src[0]), Number(src[1]), Number(src[2]));
}

function eulerDeg(arr) {
  const src = Array.isArray(arr) ? arr : [0, 0, 0];
  return new THREE.Euler(
    THREE.MathUtils.degToRad(Number(src[0])),
    THREE.MathUtils.degToRad(Number(src[1])),
    THREE.MathUtils.degToRad(Number(src[2]))
  );
}

function roomSpec(env, meshType) {
  const room = env?.room || {};
  if (meshType === "cave_shell") {
    return {
      width: Number(room.width) || 10,
      depth: Number(room.depth) || 7,
      height: Number(room.height) || 5,
    };
  }
  return null;
}

function alignSurfaces(surfaces, env, meshType) {
  const room = roomSpec(env, meshType);
  if (!room) return surfaces;

  const { width: W, depth: D, height: H } = room;
  const backZ = -D / 2;
  const pad = CAVE_OVERLAP;
  const byId = Object.fromEntries(surfaces.map((s) => [s.id, { ...s }]));

  const layouts = {
    back: {
      size: [W + pad, H + pad],
      position: [0, H / 2, backZ],
      rotation: [0, 0, 0],
    },
    left: {
      size: [D + pad, H + pad],
      position: [-W / 2, H / 2, 0],
      rotation: [0, 90, 0],
    },
    right: {
      size: [D + pad, H + pad],
      position: [W / 2, H / 2, 0],
      rotation: [0, -90, 0],
    },
    floor: {
      size: [W + pad * 2, D + pad * 2],
      position: [0, 0, 0],
      rotation: [-90, 0, 0],
    },
    ground: {
      size: [W + pad * 2, D + pad * 2],
      position: [0, 0.01, 0],
      rotation: [-90, 0, 0],
    },
  };

  return surfaces.map((surface) => {
    const layout = layouts[surface.id];
    if (!layout) return byId[surface.id] || surface;
    return { ...(byId[surface.id] || surface), ...layout };
  });
}

function surfacesFromPanorama(sceneData) {
  const env = sceneData.environment || {};
  const meshType = env.mesh || "open_ground";
  const crops = sceneData.panorama_crops || {};
  const layouts = env.surfaces || [];
  const surfaces = layouts
    .filter((layout) => crops[layout.id])
    .map((layout) => ({
      id: layout.id,
      panorama_crop: crops[layout.id],
      source: "master",
    }));
  return alignSurfaces(surfaces, env, meshType);
}

function surfaceUrl(apiBase, gameId, surface) {
  const base = apiBase.replace(/\/$/, "");
  const extra = surface.params || {};
  if (surface.panorama) {
    const params = new URLSearchParams();
    if (extra.region_id) params.set("region_id", extra.region_id);
    const qs = params.toString();
    const sid = encodeURIComponent(surface.id);
    return `${base}/games/${gameId}/world/scene/panorama/${sid}${qs ? `?${qs}` : ""}`;
  }
  const type = encodeURIComponent(surface.visual_type || "region");
  const id = encodeURIComponent(surface.visual_id || "");
  if (surface.standard_visual) {
    return `${base}/games/${gameId}/visuals/${type}/${id}`;
  }
  const params = new URLSearchParams();
  if (extra.context) params.set("context", extra.context);
  if (extra.template_id) params.set("template_id", extra.template_id);
  if (extra.surface) params.set("surface", extra.surface);
  if (extra.region_id) params.set("region_id", extra.region_id);
  const qs = params.toString();
  return `${base}/games/${gameId}/visuals/${type}/${id}${qs ? `?${qs}` : ""}`;
}

function applyEnvironment(scene, env, meshType) {
  scene.background = new THREE.Color(env.background || "#0f1419");
  if (env.fog) {
    scene.fog = new THREE.Fog(
      env.fog.color || "#1a2332",
      env.fog.near ?? 2,
      env.fog.far ?? 14
    );
  } else if (meshType === "cave_shell") {
    scene.fog = new THREE.Fog("#1a2332", 2, 14);
  }
}

function placeholderMaterial(meshType, surfaceId) {
  if (surfaceId === "floor" || surfaceId === "ground") {
    return new THREE.MeshStandardMaterial({
      color: meshType === "cave_shell" ? 0x2a3548 : 0x4a5d42,
      roughness: 0.95,
    });
  }
  return new THREE.MeshStandardMaterial({
    color: meshType === "cave_shell" ? 0x1a2332 : 0x5a6a78,
    roughness: 1,
  });
}

function addSurfaceMesh(scene, surface, meshType) {
  const size = surface.size || [10, 5];
  const width = Number(size[0]) || 10;
  const height = Number(size[1]) || 5;
  const mat = placeholderMaterial(meshType, surface.id);
  const mesh = new THREE.Mesh(new THREE.PlaneGeometry(width, height), mat);
  mesh.position.copy(vec3(surface.position));
  mesh.rotation.copy(eulerDeg(surface.rotation));
  mesh.renderOrder = surface.id === "back" ? 0 : 1;
  if (surface.id === "floor" || surface.id === "ground") {
    mesh.receiveShadow = true;
  }
  scene.add(mesh);
  return mesh;
}

function cropImageTexture(image, rect) {
  const w = image.naturalWidth || image.width;
  const h = image.naturalHeight || image.height;
  const cw = Math.max(1, Math.round(w * rect.w));
  const ch = Math.max(1, Math.round(h * rect.h));
  const canvas = document.createElement("canvas");
  canvas.width = cw;
  canvas.height = ch;
  const ctx = canvas.getContext("2d");
  ctx.drawImage(
    image,
    Math.round(w * rect.x),
    Math.round(h * rect.y),
    Math.round(w * rect.w),
    Math.round(h * rect.h),
    0,
    0,
    cw,
    ch
  );
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

function applyTexture(mesh, texture) {
  const oldMat = mesh.material;
  mesh.material = new THREE.MeshBasicMaterial({
    map: texture,
    side: THREE.DoubleSide,
  });
  oldMat.dispose();
}

function loadSurfaceTexture(mesh, url) {
  return new Promise((resolve) => {
    const loader = new THREE.TextureLoader();
    loader.setCrossOrigin("anonymous");
    loader.load(
      url,
      (texture) => {
        texture.colorSpace = THREE.SRGBColorSpace;
        applyTexture(mesh, texture);
        resolve(true);
      },
      undefined,
      () => resolve(false)
    );
  });
}

function addEntityPrimitive(scene, entity) {
  const pos = vec3(entity.position);
  const primitive = entity.primitive || "default";
  let mesh;
  if (primitive === "ember_glow") {
    const core = new THREE.Mesh(
      new THREE.SphereGeometry(0.22, 16, 16),
      new THREE.MeshStandardMaterial({
        color: 0xff6a1a,
        emissive: 0xff4500,
        emissiveIntensity: 1.2,
      })
    );
    core.position.copy(pos);
    core.position.y += 0.22;
    scene.add(core);
    const light = new THREE.PointLight(0xff6a1a, 1.4, 4);
    light.position.copy(core.position);
    scene.add(light);
    return { mesh: core, light };
  }
  if (primitive === "pool") {
    mesh = new THREE.Mesh(
      new THREE.CylinderGeometry(0.55, 0.65, 0.08, 24),
      new THREE.MeshStandardMaterial({
        color: 0x3d9ee8,
        roughness: 0.2,
        metalness: 0.1,
      })
    );
    mesh.position.copy(pos);
    mesh.position.y += 0.04;
    scene.add(mesh);
    return { mesh };
  }
  mesh = new THREE.Mesh(
    new THREE.BoxGeometry(0.5, 0.5, 0.5),
    new THREE.MeshStandardMaterial({ color: 0x8b7355, roughness: 0.85 })
  );
  mesh.position.copy(pos);
  mesh.position.y += 0.25;
  scene.add(mesh);
  return { mesh };
}

function addExitMesh(scene, layout, exits, env, meshType, sceneData) {
  if (!layout || !exits?.length) return null;
  const open =
    exits.find((e) => e.status === "open") || exits.find((e) => e.status === "found");
  if (!open) return null;

  const meshKind = layout.mesh || "passage_arch";
  const wall = layout.wall || "right";
  if (
    wall === "back" &&
    meshKind === "passage_arch" &&
    (sceneData?.scene_mode === "single_scene" ||
      sceneData?.surfaces?.some(
        (s) => s.id === "back" && (s.standard_visual || s.panorama)
      ))
  ) {
    return null;
  }

  const color = open.status === "open" ? 0xc9a66b : 0x6a5a48;
  const mat = new THREE.MeshStandardMaterial({
    color,
    roughness: 0.85,
    emissive: 0x221100,
    emissiveIntensity: open.status === "open" ? 0.15 : 0,
  });
  const room = roomSpec(env, meshType);
  const offset = layout.position || [2.2, 0, 0.2];
  let mesh;

  if (meshKind === "passage_arch" && wall === "back" && room) {
    const ox = Number(offset[0]) || 0;
    const oy = Number(offset[1]) || 0;
    const backZ = -room.depth / 2;
    mesh = new THREE.Mesh(
      new THREE.TorusGeometry(0.42, 0.07, 10, 24, Math.PI),
      mat
    );
    mesh.position.set(ox, room.height / 2 + oy, backZ + 0.08);
    mesh.rotation.z = Math.PI;
    scene.add(mesh);
    if (open.status === "open") {
      const daylight = new THREE.PointLight(0xfff0cc, 0.55, 4);
      daylight.position.set(ox, room.height / 2 + oy + 0.1, backZ - 0.35);
      scene.add(daylight);
    }
    return mesh;
  }

  if (meshKind === "cave_mouth") {
    mesh = new THREE.Mesh(new THREE.BoxGeometry(1.2, 1.6, 0.35), mat);
    mesh.position.copy(vec3(offset, [-2.4, 0, 0.8]));
    mesh.position.y += 0.8;
    scene.add(mesh);
    return mesh;
  }

  const pos = vec3(offset, [2.2, 0, 0.2]);
  mesh = new THREE.Mesh(new THREE.TorusGeometry(0.55, 0.12, 10, 20, Math.PI), mat);
  mesh.rotation.z = Math.PI;
  mesh.rotation.y = -Math.PI / 2;
  mesh.position.copy(pos);
  mesh.position.y += 0.55;
  scene.add(mesh);
  return mesh;
}

function disposeScene(state) {
  if (!state) return;
  if (state.animationId) cancelAnimationFrame(state.animationId);
  if (state.resizeHandler) window.removeEventListener("resize", state.resizeHandler);
  if (state.renderer) {
    state.renderer.dispose();
    if (state.canvas?.parentNode) state.canvas.parentNode.removeChild(state.canvas);
  }
  if (state.scene) {
    state.scene.traverse((obj) => {
      if (obj.geometry) obj.geometry.dispose();
      if (obj.material) {
        if (obj.material.map) obj.material.map.dispose();
        if (Array.isArray(obj.material)) obj.material.forEach((m) => m.dispose());
        else obj.material.dispose();
      }
    });
  }
}

function setStatus(state, message) {
  if (state?.statusEl) state.statusEl.textContent = message || "";
}

async function paintPanoramaSurfaces(scene, surfaces, masterImg, meshType, regionName, stateRef) {
  if (!surfaces?.length || !masterImg) return;
  const meshes = surfaces.map((surface) => ({
    surface,
    mesh: addSurfaceMesh(scene, surface, meshType),
  }));

  let loaded = 0;
  const total = meshes.length;
  setStatus(stateRef, `Painting ${regionName}… (0/${total})`);

  for (const { surface, mesh } of meshes) {
    if (!active || active !== stateRef) return;
    try {
      const texture = cropImageTexture(masterImg, surface.panorama_crop);
      applyTexture(mesh, texture);
      loaded += 1;
      setStatus(stateRef, `Painting ${regionName}… (${loaded}/${total})`);
    } catch (_err) {
      loaded += 1;
      setStatus(
        stateRef,
        `Painting ${regionName}… (${loaded}/${total}, ${surface.id} procedural)`
      );
    }
  }

  if (active === stateRef) setStatus(stateRef, "");
}

async function paintSurfaces(scene, surfaces, ctx, meshType, regionName, stateRef) {
  if (!surfaces?.length) return;
  const meshes = surfaces.map((surface) => ({
    surface,
    mesh: addSurfaceMesh(scene, surface, meshType),
  }));

  let loaded = 0;
  const total = meshes.length;
  setStatus(stateRef, `Painting ${regionName}… (0/${total})`);

  await Promise.all(
    meshes.map(async ({ surface, mesh }) => {
      const url = surfaceUrl(ctx.apiBase, ctx.gameId, surface);
      const ok = await loadSurfaceTexture(mesh, url);
      if (!active || active !== stateRef) return;
      loaded += 1;
      if (ok) {
        setStatus(stateRef, `Painting ${regionName}… (${loaded}/${total})`);
      } else {
        setStatus(
          stateRef,
          `Painting ${regionName}… (${loaded}/${total}, ${surface.id} procedural)`
        );
      }
      if (loaded >= total) setStatus(stateRef, "");
    })
  );
}

async function mount(container, ctx) {
  dispose();
  if (!container || !ctx?.apiBase || !ctx?.gameId) return;

  const gfx = window.WhatGraphics;
  if (!gfx?.ensureSceneImage) {
    setStatus(
      { statusEl: container.querySelector(".world-scene-status") },
      "Could not load scene."
    );
    return;
  }

  const statusEl = container.querySelector(".world-scene-status");
  const host = container.querySelector(".world-scene-host") || container;
  setStatus({ statusEl }, "Loading scene…");

  let sceneData;
  let masterImg = null;
  try {
    const entry = await gfx.ensureSceneImage(ctx, ctx.regionId);
    sceneData = entry.sceneData;
    masterImg = entry.img;
  } catch (_err) {
    setStatus({ statusEl }, "Could not generate cave scene.");
    return;
  }

  const env = sceneData.environment || {};
  const camSpec = sceneData.camera || {};
  const meshType = env.mesh || "open_ground";
  const usePanoramaRoom =
    sceneData.scene_mode === "single_scene" &&
    masterImg &&
    Object.keys(sceneData.panorama_crops || {}).length > 0;
  const surfaces = usePanoramaRoom
    ? surfacesFromPanorama(sceneData)
    : alignSurfaces(sceneData.surfaces || [], env, meshType);

  host.innerHTML = "";
  const canvas = document.createElement("canvas");
  canvas.className = "world-scene-canvas";
  canvas.setAttribute("aria-hidden", "true");
  host.appendChild(canvas);

  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.shadowMap.enabled = true;

  const scene = new THREE.Scene();
  applyEnvironment(scene, env, meshType);

  const camera = new THREE.PerspectiveCamera(camSpec.fov || 50, 1, 0.1, 50);
  camera.position.copy(vec3(camSpec.position, [0, 1.8, 5]));
  camera.lookAt(vec3(camSpec.look_at, [0, 0.5, 0]));

  const ambient = new THREE.AmbientLight(0xffffff, env.ambient ?? 0.45);
  scene.add(ambient);
  const sun = new THREE.DirectionalLight(
    0xfff0dd,
    meshType === "open_ground" ? 0.9 : 0.55
  );
  sun.position.set(2, 6, 4);
  sun.castShadow = true;
  scene.add(sun);

  const entityLights = [];
  (sceneData.slot_entities || []).forEach((entity) => {
    const built = addEntityPrimitive(scene, entity);
    if (built?.light) entityLights.push(built.light);
  });
  addExitMesh(scene, sceneData.exit_layout, sceneData.exits, env, meshType, sceneData);

  const stateRef = {
    container,
    host,
    statusEl,
    canvas,
    renderer,
    scene,
    camera,
    entityLights,
    animationId: null,
    resizeHandler: null,
    startTime: performance.now(),
  };
  active = stateRef;

  function resize() {
    if (!active) return;
    const width = Math.max(1, host.clientWidth || 640);
    const height = Math.max(1, host.clientHeight || Math.round(width * (2 / 3)));
    active.renderer.setSize(width, height, false);
    active.canvas.style.width = "100%";
    active.canvas.style.height = "100%";
    active.camera.aspect = width / height;
    active.camera.updateProjectionMatrix();
  }
  active.resizeHandler = resize;
  window.addEventListener("resize", resize);
  resize();

  function tick(now) {
    if (!active) return;
    const t = (now - active.startTime) / 1000;
    active.entityLights.forEach((light, i) => {
      light.intensity = 1.2 + Math.sin(t * 3 + i) * 0.25;
    });
    active.renderer.render(active.scene, active.camera);
    active.animationId = requestAnimationFrame(tick);
  }
  active.animationId = requestAnimationFrame(tick);

  const regionName = sceneData.region?.name || "region";
  if (usePanoramaRoom) {
    await paintPanoramaSurfaces(
      scene,
      surfaces,
      masterImg,
      meshType,
      regionName,
      stateRef
    );
  } else {
    paintSurfaces(scene, surfaces, ctx, meshType, regionName, stateRef);
  }
}

function dispose() {
  if (!active) return;
  const host = active.host;
  disposeScene(active);
  if (host) host.innerHTML = "";
  active = null;
}

window.WhatBasic3D = { mount, dispose };
