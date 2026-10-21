/**
 * JARVIS · CHEN // OS - 3D 全息浮雕引擎（支持真实上下唇分离与口腔内腔开合）
 */

class JarvisReactor {
  constructor(containerId, imageUrl = "./icon.png") {
    this.container = document.getElementById(containerId);
    this.imageUrl = imageUrl;

    this.scene = null;
    this.camera = null;
    this.renderer = null;
    this.headGroup = null;

    // 3D 网格与真实口型开合组件
    this.hologramMesh = null;
    this.wireframeOverlay = null;
    this.hudRing = null;

    this.origPositions = null;
    this.jawWeights = null;      // 下唇与下巴向下张开的权重 (0 ~ 1)
    this.upperLipWeights = null; // 上唇微微上提的权重 (0 ~ 1)

    // 状态与音频控制
    this.currentState = "standby";
    this.audioIntensity = 0;
    this.mouthOpenAmount = 0;
    this.clock = new THREE.Clock();

    // 鼠标 3D 视角追踪
    this.targetRotationY = 0;
    this.targetRotationX = 0;
    this.currentRotationY = 0;
    this.currentRotationX = 0;

    this.stateColors = {
      standby: 0x00f3ff,
      listening: 0x00ff88,
      thinking: 0xbd00ff,
      executing: 0xffaa00
    };

    this.init();
  }

  init() {
    if (!this.container) return;
    const width = this.container.clientWidth || 600;
    const height = this.container.clientHeight || 500;

    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(42, width / height, 0.1, 1000);
    this.camera.position.set(0, 0, 155);

    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    this.renderer.setSize(width, height);
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.container.innerHTML = "";
    this.container.appendChild(this.renderer.domElement);

    this.headGroup = new THREE.Group();
    this.scene.add(this.headGroup);

    this.build3DFromImage(this.imageUrl);

    window.addEventListener("resize", () => this.onWindowResize());
    this.container.addEventListener("mousemove", (e) => this.onMouseMove(e));
    this.container.addEventListener("mouseleave", () => {
      this.targetRotationY = 0;
      this.targetRotationX = 0;
    });

    this.animate();
  }


  build3DFromImage(url) {
    const img = new Image();
    img.crossOrigin = "Anonymous";
    img.onload = () => {
      const size = 512;
      const canvas = document.createElement("canvas");
      canvas.width = size;
      canvas.height = size;
      const ctx = canvas.getContext("2d");

      ctx.drawImage(img, 0, 0, size, size);
      const imgData = ctx.getImageData(0, 0, size, size);
      const data = imgData.data;

      const heightMap = new Float32Array(size * size);

      for (let y = 0; y < size; y++) {
        for (let x = 0; x < size; x++) {
          const idx = (y * size + x) * 4;
          const r = data[idx];
          const g = data[idx + 1];
          const b = data[idx + 2];

          const luma = (r * 0.299 + g * 0.587 + b * 0.114) / 255;
          const cyanGlow = Math.max(0, (b - r * 0.5) / 255);
          const goldGlow = Math.max(0, (r - b * 0.5) / 255);
          const intensity = Math.min(1.0, luma * 1.1 + cyanGlow * 0.5 + goldGlow * 0.5);

          heightMap[y * size + x] = intensity;

          const nx = (x / size) * 2 - 1;
          const ny = (y / size) * 2 - 1;
          const distFromEdge = Math.max(Math.abs(nx), Math.abs(ny));

          if (distFromEdge > 0.78 || intensity < 0.14) {
            data[idx + 3] = 0;
          } else {
            data[idx + 3] = Math.min(255, Math.pow(intensity, 0.75) * 255);
          }
        }
      }

      ctx.putImageData(imgData, 0, 0);
      const hologramTexture = new THREE.CanvasTexture(canvas);
      hologramTexture.minFilter = THREE.LinearFilter;

      // 提高网格细分度到 180x180，使上下唇分离边缘更锐利平滑
      const segs = 180;
      const geo = new THREE.PlaneGeometry(115, 115, segs, segs);
      const posAttr = geo.attributes.position;
      const uvAttr = geo.attributes.uv;
      const vCount = posAttr.count;

      this.jawWeights = new Float32Array(vCount);
      this.upperLipWeights = new Float32Array(vCount);

      for (let i = 0; i < vCount; i++) {
        const u = uvAttr.getX(i);
        const v = uvAttr.getY(i);

        const px = Math.min(size - 1, Math.floor(u * size));
        const py = Math.min(size - 1, Math.floor((1 - v) * size));
        const pixelBrightness = heightMap[py * size + px];

        // 归一化中心坐标 cx, cy (-1 ~ 1)
        const cx = (u - 0.5) * 2;
        const cy = (v - 0.5) * 2;

        // 1. 头部整体 3D 体积感
        const headRadiusDist = Math.hypot(cx * 1.15, (cy - 0.05) * 0.9);
        let zVolume = 0;
        if (headRadiusDist < 0.75) {
          zVolume = Math.cos(headRadiusDist * Math.PI * 0.65) * 18.0;
        }

        // 2. 五官立体凸起
        const noseDist = Math.hypot(cx - (-0.22), (cy - 0.02) * 0.7);
        const noseBump = Math.max(0, 1 - noseDist / 0.22) * 8.5;

        const eyeDist = Math.hypot((cx - (-0.12)) * 0.8, cy - 0.14);
        const eyeSocket = Math.max(0, 1 - eyeDist / 0.25) * 3.5;

        const earDist = Math.hypot(cx - 0.34, cy - 0.06);
        const earBump = Math.max(0, 1 - earDist / 0.22) * 7.5;

        const lineRelief = pixelBrightness * 5.2;
        const finalZ = zVolume + noseBump + eyeSocket + earBump + lineRelief;
        posAttr.setZ(i, finalZ);

        // ====================================================================
        // 3. 【核心改进】真人级上下唇分离与整块下颌骨（Jaw）开合权重计算
        // ====================================================================
        // 原图中嘴唇中心位于 cx ≈ -0.225, 上下唇闭合中线位于 cy ≈ -0.205
        const lipCenterX = -0.225;
        // 顺着原图嘴角弧度计算唇缝分界线 Y 坐标
        const seamY = -0.205 + Math.pow(cx - lipCenterX, 2) * 0.45;
        const horizDist = Math.abs(cx - lipCenterX);

        // A. 上嘴唇区域（唇缝上方一点点）：说话时微微向上提，露出上唇动作
        if (horizDist < 0.15 && cy >= seamY && cy < seamY + 0.055) {
          const hFactor = Math.cos((horizDist / 0.15) * Math.PI * 0.5);
          const vFactor = 1.0 - (cy - seamY) / 0.055;
          this.upperLipWeights[i] = hFactor * vFactor;
        }

        // B. 下嘴唇 + 整块机械下巴区域（唇缝下方）：作为一个刚体整体向下张开！
        // 纵向范围涵盖从唇缝 (seamY) 一直到下巴底端 (-0.47)
        if (horizDist < 0.21 && cy < seamY && cy > -0.47) {
          // 横向平滑过渡：嘴巴正中央张开最大，向两侧下颌装甲边缘自然衰减
          const hFactor = Math.pow(Math.cos((horizDist / 0.21) * Math.PI * 0.5), 1.2);

          // 纵向刚体权重：下嘴唇到下巴尖保持高权重整体下移，使唇缝瞬间“裂开”而不是拉面条
          let vFactor = 1.0;
          if (cy < -0.36) {
            // 下巴最底部与脖子交界处平滑过渡，防止脖子断裂
            vFactor = Math.max(0, (cy - (-0.47)) / 0.11);
          }
          this.jawWeights[i] = hFactor * vFactor;
        }
      }

      posAttr.needsUpdate = true;
      this.origPositions = new Float32Array(posAttr.array);

      // 1. 主体全息发光网格
      const mat = new THREE.MeshBasicMaterial({
        map: hologramTexture,
        transparent: true,
        opacity: 0.96,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
        side: THREE.DoubleSide
      });
      this.hologramMesh = new THREE.Mesh(geo, mat);
      this.headGroup.add(this.hologramMesh);

      // 2. 3D 科技线框叠加层
      const wireMat = new THREE.MeshBasicMaterial({
        color: 0x00f3ff,
        map: hologramTexture,
        wireframe: true,
        transparent: true,
        opacity: 0.18,
        blending: THREE.AdditiveBlending,
        depthWrite: false
      });
      this.wireframeOverlay = new THREE.Mesh(geo, wireMat);
      this.wireframeOverlay.position.z = 0.4;
      this.headGroup.add(this.wireframeOverlay);
    };

    img.src = url;

    // 底部全息环
    const ringGeo = new THREE.RingGeometry(58, 58.6, 64);
    const ringMat = new THREE.MeshBasicMaterial({
      color: 0x00f3ff,
      side: THREE.DoubleSide,
      transparent: true,
      opacity: 0.25,
      blending: THREE.AdditiveBlending
    });
    this.hudRing = new THREE.Mesh(ringGeo, ringMat);
    this.hudRing.rotation.x = Math.PI / 2.3;
    this.hudRing.position.y = -12;
    this.headGroup.add(this.hudRing);
  }

  onMouseMove(e) {
    if (!this.container) return;
    const rect = this.container.getBoundingClientRect();
    const nx = (e.clientX - rect.left) / rect.width - 0.5;
    const ny = (e.clientY - rect.top) / rect.height - 0.5;

    this.targetRotationY = nx * 0.55;
    this.targetRotationX = ny * 0.35;
  }

  onWindowResize() {
    if (!this.container || !this.renderer) return;
    const width = this.container.clientWidth;
    const height = this.container.clientHeight;
    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(width, height);
  }

  setState(state) {
    const hex = this.stateColors[state] || 0x00f3ff;
    this.currentState = state;
    if (this.wireframeOverlay) this.wireframeOverlay.material.color.setHex(hex);
    if (this.hudRing) this.hudRing.material.color.setHex(hex);
  }

  updateAudioIntensity(intensity) {
    this.audioIntensity = intensity;
  }

  animate() {
    requestAnimationFrame(() => this.animate());
    const time = this.clock.getElapsedTime();

    // 1. 模拟真人说话的多频音节开合节奏（复合正弦波模拟自然语速的顿挫与完全闭合瞬间）
    let targetMouth = 0;
    if (this.audioIntensity > 0.02) {
      // 组合快慢两个音节频率，让嘴巴有真实的“张大 -> 半闭 -> 完全闭合 -> 张开”节奏
      const syllableWave = Math.sin(time * 16.0) * 0.5 + Math.sin(time * 27.0) * 0.35 + 0.35;
      const clampedWave = Math.max(0, syllableWave); // 确保音节间隙嘴巴能完全合拢
      targetMouth = Math.min(1.0, this.audioIntensity * 2.4) * clampedWave;
    }

    // 加快插值响应速度 (0.45)，让嘴唇闭合干脆利落，不拖泥带水
    this.mouthOpenAmount = THREE.MathUtils.lerp(this.mouthOpenAmount, targetMouth, 0.45);

    if (this.hologramMesh && this.origPositions) {
      const pos = this.hologramMesh.geometry.attributes.position.array;
      const orig = this.origPositions;
      const jWeights = this.jawWeights;
      const uWeights = this.upperLipWeights;
      const count = jWeights.length;

      for (let i = 0; i < count; i++) {
        const jw = jWeights[i];
        const uw = uWeights[i];

        if (jw > 0 || uw > 0) {
          const idx = i * 3;
          // 上唇微微上抬 (最高约 1.2 单位)，下唇与下巴大幅度向下张开 (最高约 6.5 单位)
          const deltaY = (uw * 1.2 - jw * 6.5) * this.mouthOpenAmount;
          // 下巴张开时符合人体工学微微向后内收，同时唇缘高光微凸
          const deltaZ = (uw * 0.6 - jw * 1.8) * this.mouthOpenAmount;

          pos[idx + 1] = orig[idx + 1] + deltaY;
          pos[idx + 2] = orig[idx + 2] + deltaZ;
        }
      }
      this.hologramMesh.geometry.attributes.position.needsUpdate = true;

    }

    // 2. 头部悬浮呼吸与鼠标 3D 视差追踪
    const floatY = Math.sin(time * 1.5) * 1.8;
    const idleYaw = Math.sin(time * 0.7) * 0.06;
    const idlePitch = Math.cos(time * 1.0) * 0.03;

    this.currentRotationY = THREE.MathUtils.lerp(this.currentRotationY, this.targetRotationY + idleYaw, 0.06);
    this.currentRotationX = THREE.MathUtils.lerp(this.currentRotationX, this.targetRotationX + idlePitch, 0.06);

    if (this.headGroup) {
      this.headGroup.position.y = floatY;
      this.headGroup.rotation.y = this.currentRotationY;
      this.headGroup.rotation.x = this.currentRotationX;
    }

    // 3. 光环自转与声波脉冲
    if (this.hudRing) {
      this.hudRing.rotation.z += 0.004;
      this.hudRing.material.opacity = 0.2 + this.audioIntensity * 0.35;
    }
    if (this.wireframeOverlay) {
      this.wireframeOverlay.material.opacity = 0.15 + this.audioIntensity * 0.25;
    }

    this.renderer.render(this.scene, this.camera);
  }
}
