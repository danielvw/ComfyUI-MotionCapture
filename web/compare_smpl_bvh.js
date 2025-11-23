/**
 * Compare SMPL to BVH Viewer
 * Side-by-side comparison of SMPL mesh and BVH skeleton using Split View (Scissor Test)
 */

import { app } from "../../scripts/app.js";

const COMPARE_VIEWER_HTML = `
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        html, body { width: 100%; height: 100%; margin: 0; padding: 0; overflow: hidden; background: #1a1a1a; font-family: Arial, sans-serif; }
        #container { display: flex; flex-direction: column; width: 100%; height: 100%; }
        #canvas-container { flex: 1; position: relative; overflow: hidden; width: 100%; min-height: 0; background: #000; }
        #controls {
            height: 40px;
            flex-shrink: 0;
            background: #252525;
            display: flex;
            align-items: center;
            padding: 0 10px;
            gap: 10px;
            border-top: 1px solid #333;
            z-index: 200;
        }
        
        /* Overlays */
        .panel-label {
            position: absolute;
            top: 10px;
            color: rgba(255, 255, 255, 0.7);
            font-weight: bold;
            font-size: 14px;
            pointer-events: none;
            background: rgba(0,0,0,0.5);
            padding: 4px 8px;
            border-radius: 4px;
            z-index: 10;
        }
        #label-smpl { left: 10px; }
        #label-bvh { left: 50%; margin-left: 10px; }
        
        #loading {
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            color: white;
            font-size: 16px;
            background: rgba(0,0,0,0.8);
            padding: 15px 20px;
            border-radius: 8px;
            z-index: 100;
        }

        /* Controls */
        button {
            background: #4a9eff;
            border: none;
            color: white;
            border-radius: 4px;
            width: 30px;
            height: 30px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 14px;
        }
        button:hover { background: #3a8eef; }
        button:disabled { background: #444; cursor: default; }
        
        input[type=range] {
            flex-grow: 1;
            height: 6px;
            background: #444;
            border-radius: 3px;
            outline: none;
        }
        
        .frame-counter {
            color: #aaa;
            font-family: monospace;
            font-size: 12px;
            min-width: 80px;
            text-align: right;
        }
    </style>
</head>
<body>
    <div id="container">
        <div id="canvas-container">
            <div id="loading">Waiting for data...</div>
            <div id="label-smpl" class="panel-label">SMPL (Mesh)</div>
            <div id="label-bvh" class="panel-label">BVH (Skeleton)</div>
        </div>
        <div id="controls">
            <button id="play-btn">▶</button>
            <input type="range" id="slider" min="0" max="0" value="0" step="1">
            <div class="frame-counter" id="frame-display">0 / 0</div>
        </div>
    </div>

    <script type="importmap">
    {
        "imports": {
            "three": "https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js",
            "three/addons/": "https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/"
        }
    }
    <\/script>

    <script type="module">
        import * as THREE from 'three';
        import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
        import { BVHLoader } from 'three/addons/loaders/BVHLoader.js';

        console.log("[CompareViewer] Script starting...");

        let renderer, camera, controls;
        let sceneSMPL, sceneBVH;
        
        // Data State
        let smplData = null;
        let smplMesh = null;
        
        let bvhHelper = null;
        let bvhMixer = null;
        let bvhAction = null;
        let bvhSkeleton = null;
        
        // Playback State
        let isPlaying = false;
        let currentFrame = 0;
        let totalFrames = 0;
        let fps = 30;
        let clock = new THREE.Clock();

        const slider = document.getElementById('slider');
        const frameDisplay = document.getElementById('frame-display');
        const playBtn = document.getElementById('play-btn');

        function init() {
            console.log("[CompareViewer] initializing...");
            const container = document.getElementById('canvas-container');
            const w = container.clientWidth;
            const h = container.clientHeight;
            console.log("[CompareViewer] Container size:", w, h);

            // Renderer
            renderer = new THREE.WebGLRenderer({ antialias: true });
            renderer.setSize(w, h);
            renderer.setPixelRatio(window.devicePixelRatio);
            renderer.setScissorTest(true);
            container.appendChild(renderer.domElement);

            // Camera (Shared)
            camera = new THREE.PerspectiveCamera(50, w / h, 0.01, 100);
            camera.position.set(0, 1.5, 4);

            // Controls (Shared)
            controls = new OrbitControls(camera, renderer.domElement);
            controls.target.set(0, 1, 0);
            controls.enableDamping = true;

            // -- Scene 1: SMPL --
            sceneSMPL = new THREE.Scene();
            sceneSMPL.background = new THREE.Color(0x111111);
            setupSceneCommon(sceneSMPL);

            // -- Scene 2: BVH --
            sceneBVH = new THREE.Scene();
            sceneBVH.background = new THREE.Color(0x1a1a1a);
            setupSceneCommon(sceneBVH);

            // Listeners
            window.addEventListener('resize', onWindowResize);
            window.addEventListener('message', handleMessage);
            
            // UI Listeners
            playBtn.onclick = togglePlay;
            slider.oninput = (e) => {
                pause();
                seek(parseInt(e.target.value));
            };

            animate();
            console.log("[CompareViewer] Init complete, animation loop started.");
        }

        function setupSceneCommon(scene) {
            // Grid
            const grid = new THREE.GridHelper(10, 10, 0x444444, 0x222222);
            scene.add(grid);
            scene.add(new THREE.AxesHelper(0.5));

            // Lights
            const dirLight = new THREE.DirectionalLight(0xffffff, 1.5);
            dirLight.position.set(2, 5, 5);
            scene.add(dirLight);
            
            const ambLight = new THREE.AmbientLight(0xffffff, 0.6);
            scene.add(ambLight);
        }

        function onWindowResize() {
            const container = document.getElementById('canvas-container');
            const w = container.clientWidth;
            const h = container.clientHeight;
            console.log("[CompareViewer] Resize:", w, h);
            
            if (w === 0 || h === 0) return;

            // Aspect ratio for half width
            camera.aspect = (w * 0.5) / h;
            camera.updateProjectionMatrix();
            renderer.setSize(w, h);
        }

        // --- Logic ---

        function togglePlay() {
            if (isPlaying) pause(); else play();
        }

        function play() {
            isPlaying = true;
            playBtn.textContent = "⏸";
            clock.start();
        }

        function pause() {
            isPlaying = false;
            playBtn.textContent = "▶";
        }

        function seek(frame) {
            currentFrame = Math.max(0, Math.min(frame, totalFrames - 1));
            updateVisuals(currentFrame);
            updateUI();
        }

        function updateUI() {
            slider.value = Math.floor(currentFrame);
            frameDisplay.textContent = Math.floor(currentFrame) + ' / ' + totalFrames;
        }

        function updateVisuals(frame) {
            const time = frame / fps;

            // SMPL
            if (smplMesh && smplData) {
                const f = Math.min(Math.floor(frame), smplData.numFrames - 1);
                const start = f * smplData.numVerts * 3;
                const end = start + smplData.numVerts * 3;
                const frameVerts = smplData.vertices.subarray(start, end);
                smplMesh.geometry.attributes.position.array.set(frameVerts);
                smplMesh.geometry.attributes.position.needsUpdate = true;
                smplMesh.geometry.computeVertexNormals();
            }

            // BVH
            if (bvhMixer) {
                bvhMixer.setTime(time);
            }
        }

        function animate() {
            requestAnimationFrame(animate);
            controls.update();

            if (isPlaying && totalFrames > 0) {
                const delta = clock.getDelta();
                currentFrame += delta * fps;
                if (currentFrame >= totalFrames) currentFrame = 0; // Loop
                updateVisuals(currentFrame);
                updateUI();
            }

            renderSplitScreen();
        }

        function renderSplitScreen() {
            const container = document.getElementById('canvas-container');
            const w = container.clientWidth;
            const h = container.clientHeight;
            
            if (w === 0 || h === 0) return;

            // 1. Render Left (SMPL)
            renderer.setViewport(0, 0, w / 2, h);
            renderer.setScissor(0, 0, w / 2, h);
            renderer.render(sceneSMPL, camera);

            // 2. Render Right (BVH)
            renderer.setViewport(w / 2, 0, w / 2, h);
            renderer.setScissor(w / 2, 0, w / 2, h);
            renderer.render(sceneBVH, camera);
        }

        // --- Data Loading ---

        async function handleMessage(event) {
            console.log("[CompareViewer] Message received:", event.data.type);
            const data = event.data;
            if (data.type === 'loadData') {
                await loadAllData(data.smplFilename, data.bvhContent);
            }
        }

        async function loadAllData(smplFilename, bvhContent) {
            const loading = document.getElementById('loading');
            loading.style.display = 'block';
            loading.textContent = "Loading data...";
            
            console.log("[CompareViewer] Loading data...");
            pause();
            currentFrame = 0;
            totalFrames = 0;

            try {
                // Load SMPL
                if (smplFilename) {
                    console.log("[CompareViewer] Fetching SMPL:", smplFilename);
                    const res = await fetch('/motioncapture/smpl_mesh?filename=' + smplFilename);
                    const buf = await res.arrayBuffer();
                    parseSMPL(buf);
                }

                // Load BVH
                if (bvhContent) {
                    console.log("[CompareViewer] Parsing BVH...");
                    parseBVH(bvhContent);
                }

                // Init UI
                slider.max = totalFrames - 1;
                updateVisuals(0);
                updateUI();
                
                loading.style.display = 'none';
                console.log("[CompareViewer] Data loaded. Total frames:", totalFrames);
                
                // Trigger resize to fix aspect ratio
                onWindowResize();

            } catch (e) {
                console.error("[CompareViewer] Error loading data:", e);
                loading.textContent = "Error: " + e.message;
            }
        }

        function parseSMPL(buffer) {
            const dv = new DataView(buffer);
            let offset = 4; // Skip Magic
            const numFrames = dv.getUint32(offset, true); offset += 4;
            const numVerts = dv.getUint32(offset, true); offset += 4;
            const numFaces = dv.getUint32(offset, true); offset += 4;
            fps = dv.getFloat32(offset, true); offset += 4;

            const verts = new Float32Array(buffer, offset, numFrames * numVerts * 3);
            offset += numFrames * numVerts * 3 * 4;
            const faces = new Uint32Array(buffer, offset, numFaces * 3);

            smplData = { vertices: verts, faces: faces, numFrames, numVerts };

            // Build Mesh
            if (smplMesh) sceneSMPL.remove(smplMesh);
            
            const geo = new THREE.BufferGeometry();
            geo.setAttribute('position', new THREE.BufferAttribute(verts.subarray(0, numVerts*3), 3));
            geo.setIndex(new THREE.BufferAttribute(faces, 1));
            geo.computeVertexNormals();
            
            const mat = new THREE.MeshPhongMaterial({ color: 0x4a9eff, flatShading: false, shininess: 30, side: THREE.DoubleSide });
            smplMesh = new THREE.Mesh(geo, mat);
            sceneSMPL.add(smplMesh);

            totalFrames = Math.max(totalFrames, numFrames);
        }

        function parseBVH(content) {
            const loader = new BVHLoader();
            const result = loader.parse(content);
            
            if (bvhHelper) sceneBVH.remove(bvhHelper);
            if (bvhSkeleton) sceneBVH.remove(bvhSkeleton);

            bvhSkeleton = result.skeleton.bones[0];
            bvhHelper = new THREE.SkeletonHelper(bvhSkeleton);
            bvhHelper.material.color.setHex(0x00ff00);
            bvhHelper.material.linewidth = 3;

            sceneBVH.add(bvhSkeleton);
            sceneBVH.add(bvhHelper);

            bvhMixer = new THREE.AnimationMixer(bvhSkeleton);
            bvhAction = bvhMixer.clipAction(result.clip);
            bvhAction.play();
            
            const bvhFrames = Math.floor(result.clip.duration * fps);
            totalFrames = Math.max(totalFrames, bvhFrames);
        }

        init();
    </script>
</body>
</html>
`;

app.registerExtension({
    name: "Comfy.Compare.SMPL.BVH",
    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name === "CompareSMPLtoBVH") {
            const onNodeCreated = nodeType.prototype.onNodeCreated;
            nodeType.prototype.onNodeCreated = function() {
                const r = onNodeCreated ? onNodeCreated.apply(this, arguments) : undefined;
                
                const container = document.createElement("div");
                container.style.width = "100%";
                container.style.height = "100%";
                container.style.background = "#222";
                container.style.display = "flex";
                container.style.flexDirection = "column";
                
                const iframe = document.createElement("iframe");
                iframe.style.width = "100%";
                iframe.style.height = "100%";
                iframe.style.border = "none";
                iframe.style.flexGrow = "1";
                iframe.srcdoc = COMPARE_VIEWER_HTML;
                container.appendChild(iframe);
                
                // Add widget with computeSize for automatic resizing
                const widget = this.addDOMWidget("compare_viewer", "iframe", container);
                widget.computeSize = (w) => [w, 500]; // Fixed height for the viewer
                
                // Set an initial size for the node to accommodate the widget
                this.setSize([this.size[0], 500 + 30]);

                this.onExecuted = (msg) => {
                    if (msg?.smpl_mesh_filename && msg?.bvh_content) {
                        const send = () => {
                            iframe.contentWindow.postMessage({
                                type: 'loadData',
                                smplFilename: msg.smpl_mesh_filename[0],
                                bvhContent: msg.bvh_content[0]
                            }, '*');
                        };
                        
                        if (!iframe.contentDocument || iframe.contentDocument.readyState !== 'complete') {
                            iframe.onload = send;
                        } else {
                            send();
                        }
                    }
                };
                
                return r;
            };
        }
    }
});