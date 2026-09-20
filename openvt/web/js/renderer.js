const VERT = `#version 300 es
in vec2 in_pos; in vec2 in_uv;
uniform mat3 u_proj;
out vec2 v_uv;
void main(){ vec3 p = u_proj * vec3(in_pos, 1.0); gl_Position = vec4(p.xy, 0.0, 1.0); v_uv = in_uv; }`;

const FRAG = `#version 300 es
precision mediump float;
in vec2 v_uv;
uniform sampler2D u_tex; uniform sampler2D u_mask;
uniform int u_use_mask; uniform float u_opacity; uniform vec4 u_tint; uniform vec2 u_screen;
out vec4 frag;
void main(){
  vec4 c = texture(u_tex, v_uv) * u_tint;
  c.a *= u_opacity;
  if (u_use_mask == 1) c.a *= texture(u_mask, gl_FragCoord.xy / u_screen).a;
  frag = vec4(c.rgb * c.a, c.a);
}`;

function compile(gl, src, kind){
  const s = gl.createShader(kind);
  gl.shaderSource(s, src); gl.compileShader(s);
  if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s));
  return s;
}

export class Renderer {
  constructor(gl, model, bg = [0,0,0,0]){
    this.gl = gl; this.model = model; this.bg = bg;
    const p = gl.createProgram();
    gl.attachShader(p, compile(gl, VERT, gl.VERTEX_SHADER));
    gl.attachShader(p, compile(gl, FRAG, gl.FRAGMENT_SHADER));
    gl.bindAttribLocation(p, 0, 'in_pos'); gl.bindAttribLocation(p, 1, 'in_uv');
    gl.linkProgram(p);
    if (!gl.getProgramParameter(p, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(p));
    this.prog = p;
    this.u = {};
    for (const n of ['u_proj','u_tex','u_mask','u_use_mask','u_opacity','u_tint','u_screen'])
      this.u[n] = gl.getUniformLocation(p, n);

    this.BLEND = {
      normal:   [gl.ONE, gl.ONE_MINUS_SRC_ALPHA],
      add:      [gl.ONE, gl.ONE],
      multiply: [gl.DST_COLOR, gl.ONE_MINUS_SRC_ALPHA],
      screen:   [gl.ONE, gl.ONE_MINUS_SRC_COLOR],
    };

    gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, false);
    gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, false);
    gl.pixelStorei(gl.UNPACK_COLORSPACE_CONVERSION_WEBGL, gl.NONE);

    this.g = new Map();
    for (const L of model.layers) this.g.set(L.id, this._mk(L));

    this.w = 1; this.h = 1;
    this.maskTex = gl.createTexture(); this.fbo = gl.createFramebuffer();
    this.resize(gl.canvas.width, gl.canvas.height);
    gl.disable(gl.DEPTH_TEST); gl.enable(gl.BLEND);
  }

  _mk(L){
    const gl = this.gl;
    const vao = gl.createVertexArray(); gl.bindVertexArray(vao);
    const vbo = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, vbo);
    gl.bufferData(gl.ARRAY_BUFFER, L.basePos, gl.DYNAMIC_DRAW);
    gl.enableVertexAttribArray(0); gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);
    const uvb = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, uvb);
    gl.bufferData(gl.ARRAY_BUFFER, L.uv, gl.STATIC_DRAW);
    gl.enableVertexAttribArray(1); gl.vertexAttribPointer(1, 2, gl.FLOAT, false, 0, 0);
    const ebo = gl.createBuffer();
    gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, ebo);
    gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, L.idx, gl.STATIC_DRAW);
    gl.bindVertexArray(null);

    const tex = gl.createTexture();
    gl.bindTexture(gl.TEXTURE_2D, tex);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, L.image);
    return {vao, vbo, tex, count:L.idx.length};
  }

  resize(w, h){
    const gl = this.gl;
    this.w = Math.max(1, w|0); this.h = Math.max(1, h|0);
    gl.bindTexture(gl.TEXTURE_2D, this.maskTex);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, this.w, this.h, 0, gl.RGBA, gl.UNSIGNED_BYTE, null);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    gl.bindFramebuffer(gl.FRAMEBUFFER, this.fbo);
    gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, this.maskTex, 0);
    gl.bindFramebuffer(gl.FRAMEBUFFER, null);
  }

  _proj(){   // column-major for WebGL
    const W = this.model.width, H = this.model.height;
    const s = Math.min(this.w / W, this.h / H);
    const sx = 2 * s / this.w, sy = 2 * s / this.h;
    return new Float32Array([sx, 0, 0,  0, -sy, 0,  -W/2*sx, H/2*sy, 1]);
  }

  _mask(ids){
    const gl = this.gl;
    gl.bindFramebuffer(gl.FRAMEBUFFER, this.fbo);
    gl.viewport(0, 0, this.w, this.h);
    gl.clearColor(0, 0, 0, 0); gl.clear(gl.COLOR_BUFFER_BIT);
    gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
    gl.uniform1i(this.u.u_use_mask, 0);
    gl.uniform1f(this.u.u_opacity, 1);
    gl.uniform4f(this.u.u_tint, 1, 1, 1, 1);
    gl.activeTexture(gl.TEXTURE0);
    for (const id of ids){
      const g = this.g.get(id); if (!g || !g.count) continue;
      gl.bindTexture(gl.TEXTURE_2D, g.tex);
      gl.bindVertexArray(g.vao);
      gl.drawElements(gl.TRIANGLES, g.count, gl.UNSIGNED_INT, 0);
    }
    gl.bindFramebuffer(gl.FRAMEBUFFER, null);
  }

  draw(){
    const gl = this.gl;
    gl.viewport(0, 0, this.w, this.h);
    gl.clearColor(...this.bg); gl.clear(gl.COLOR_BUFFER_BIT);
    gl.useProgram(this.prog);
    gl.uniformMatrix3fv(this.u.u_proj, false, this._proj());
    gl.uniform2f(this.u.u_screen, this.w, this.h);
    gl.uniform1i(this.u.u_tex, 0);
    gl.uniform1i(this.u.u_mask, 1);

    for (const L of this.model.layers){
      const g = this.g.get(L.id);
      gl.bindBuffer(gl.ARRAY_BUFFER, g.vbo);
      gl.bufferSubData(gl.ARRAY_BUFFER, 0, L.curPos);
    }

    for (const L of this.model.layers){
      const g = this.g.get(L.id);
      if (!L.visible || !g.count) continue;
      let useMask = 0;
      if (L.maskedBy.length){ this._mask(L.maskedBy); useMask = 1; }
      gl.activeTexture(gl.TEXTURE1); gl.bindTexture(gl.TEXTURE_2D, this.maskTex);
      gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, g.tex);
      gl.uniform1i(this.u.u_use_mask, useMask);
      gl.uniform1f(this.u.u_opacity, L.opacity);
      gl.uniform4f(this.u.u_tint, ...L.tint);
      const b = this.BLEND[L.blend] || this.BLEND.normal;
      gl.blendFunc(b[0], b[1]);
      gl.bindVertexArray(g.vao);
      gl.drawElements(gl.TRIANGLES, g.count, gl.UNSIGNED_INT, 0);
    }
    gl.bindVertexArray(null);
  }
}