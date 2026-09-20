from __future__ import annotations
import ctypes
import numpy as np
from OpenGL.GL import *
from .shaders import VERT, FRAG

# blend funcs for premultiplied-alpha source
BLEND = {
    "normal":   (GL_ONE, GL_ONE_MINUS_SRC_ALPHA),
    "add":      (GL_ONE, GL_ONE),
    "multiply": (GL_DST_COLOR, GL_ONE_MINUS_SRC_ALPHA),
    "screen":   (GL_ONE, GL_ONE_MINUS_SRC_COLOR),
}


def _compile(src, kind):
    sh = glCreateShader(kind)
    glShaderSource(sh, src)
    glCompileShader(sh)
    if glGetShaderiv(sh, GL_COMPILE_STATUS) != GL_TRUE:
        raise RuntimeError(glGetShaderInfoLog(sh).decode())
    return sh


def build_program(vs, fs):
    prog = glCreateProgram()
    a, b = _compile(vs, GL_VERTEX_SHADER), _compile(fs, GL_FRAGMENT_SHADER)
    glAttachShader(prog, a)
    glAttachShader(prog, b)
    glLinkProgram(prog)
    if glGetProgramiv(prog, GL_LINK_STATUS) != GL_TRUE:
        raise RuntimeError(glGetProgramInfoLog(prog).decode())
    glDeleteShader(a)
    glDeleteShader(b)
    return prog


class GLLayer:
    def __init__(self, L):
        pos = np.ascontiguousarray(L.base_pos, dtype=np.float32)
        uv = np.ascontiguousarray(L.uv, dtype=np.float32)
        idx = np.ascontiguousarray(L.idx, dtype=np.uint32)
        self.count = int(idx.size)

        self.vao = glGenVertexArrays(1)
        glBindVertexArray(self.vao)
        self.vbo = glGenBuffers(1)
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
        glBufferData(GL_ARRAY_BUFFER, pos.nbytes, pos, GL_DYNAMIC_DRAW)
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 0, ctypes.c_void_p(0))
        self.uvb = glGenBuffers(1)
        glBindBuffer(GL_ARRAY_BUFFER, self.uvb)
        glBufferData(GL_ARRAY_BUFFER, uv.nbytes, uv, GL_STATIC_DRAW)
        glEnableVertexAttribArray(1)
        glVertexAttribPointer(1, 2, GL_FLOAT, GL_FALSE, 0, ctypes.c_void_p(0))
        self.ebo = glGenBuffers(1)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self.ebo)
        if self.count:
            glBufferData(GL_ELEMENT_ARRAY_BUFFER, idx.nbytes, idx, GL_STATIC_DRAW)
        glBindVertexArray(0)

        self.tex = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, self.tex)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        tw, th = L.tex_size
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, tw, th, 0, GL_RGBA, GL_UNSIGNED_BYTE, L.texture)

    def upload(self, pos):
        pos = np.ascontiguousarray(pos, dtype=np.float32)
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
        glBufferSubData(GL_ARRAY_BUFFER, 0, pos.nbytes, pos)


class Renderer:
    def __init__(self, model, w, h, bg=(0.0, 0.69, 0.25)):
        self.model = model
        self.bg = bg
        self.w, self.h = max(1, w), max(1, h)
        glPixelStorei(GL_UNPACK_ALIGNMENT, 1)
        self.prog = build_program(VERT, FRAG)
        names = ["u_proj", "u_tex", "u_mask", "u_use_mask", "u_opacity", "u_tint", "u_screen"]
        self.u = {n: glGetUniformLocation(self.prog, n) for n in names}
        self.layers = {L.id: GLLayer(L) for L in model.layers}
        self.mask_fbo = glGenFramebuffers(1)
        self.mask_tex = glGenTextures(1)
        self._alloc_mask()
        glDisable(GL_DEPTH_TEST)
        glEnable(GL_BLEND)

    def _alloc_mask(self):
        glBindTexture(GL_TEXTURE_2D, self.mask_tex)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, self.w, self.h, 0, GL_RGBA, GL_UNSIGNED_BYTE, None)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
        glBindFramebuffer(GL_FRAMEBUFFER, self.mask_fbo)
        glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, self.mask_tex, 0)
        if glCheckFramebufferStatus(GL_FRAMEBUFFER) != GL_FRAMEBUFFER_COMPLETE:
            raise RuntimeError("mask framebuffer incomplete")
        glBindFramebuffer(GL_FRAMEBUFFER, 0)

    def resize(self, w, h):
        if w <= 0 or h <= 0:
            return
        self.w, self.h = w, h
        self._alloc_mask()

    def _proj(self):
        W, H = self.model.width, self.model.height
        s = min(self.w / W, self.h / H)          # letterbox fit
        sx, sy = 2.0 * s / self.w, 2.0 * s / self.h
        return np.array([[sx, 0.0, -W / 2 * sx],
                         [0.0, -sy, H / 2 * sy],
                         [0.0, 0.0, 1.0]], dtype=np.float32)

    def _draw_layer(self, g):
        glBindVertexArray(g.vao)
        glDrawElements(GL_TRIANGLES, g.count, GL_UNSIGNED_INT, None)

    def _render_mask(self, ids):
        glBindFramebuffer(GL_FRAMEBUFFER, self.mask_fbo)
        glViewport(0, 0, self.w, self.h)
        glClearColor(0, 0, 0, 0)
        glClear(GL_COLOR_BUFFER_BIT)
        glBlendFunc(GL_ONE, GL_ONE_MINUS_SRC_ALPHA)
        glUniform1i(self.u["u_use_mask"], 0)
        glUniform1f(self.u["u_opacity"], 1.0)
        glUniform4f(self.u["u_tint"], 1, 1, 1, 1)
        glActiveTexture(GL_TEXTURE1)
        glBindTexture(GL_TEXTURE_2D, 0)
        glActiveTexture(GL_TEXTURE0)
        for mid in ids:
            g = self.layers.get(mid)
            if g is None or g.count == 0:
                continue
            glBindTexture(GL_TEXTURE_2D, g.tex)
            self._draw_layer(g)
        glBindFramebuffer(GL_FRAMEBUFFER, 0)

    def draw(self):
        glViewport(0, 0, self.w, self.h)
        glClearColor(self.bg[0], self.bg[1], self.bg[2], 1.0)
        glClear(GL_COLOR_BUFFER_BIT)
        glUseProgram(self.prog)
        glUniformMatrix3fv(self.u["u_proj"], 1, GL_TRUE, self._proj())
        glUniform2f(self.u["u_screen"], float(self.w), float(self.h))
        glUniform1i(self.u["u_tex"], 0)
        glUniform1i(self.u["u_mask"], 1)

        for L in self.model.layers:
            self.layers[L.id].upload(L.cur_pos)

        for L in self.model.layers:
            g = self.layers[L.id]
            if not L.visible or g.count == 0:
                continue
            use_mask = 0
            if L.masked_by:
                self._render_mask(L.masked_by)
                use_mask = 1
            glActiveTexture(GL_TEXTURE1)
            glBindTexture(GL_TEXTURE_2D, self.mask_tex)
            glActiveTexture(GL_TEXTURE0)
            glBindTexture(GL_TEXTURE_2D, g.tex)
            glUniform1i(self.u["u_use_mask"], use_mask)
            glUniform1f(self.u["u_opacity"], L.opacity)
            glUniform4f(self.u["u_tint"], *L.tint)
            glBlendFunc(*BLEND.get(L.blend, BLEND["normal"]))
            self._draw_layer(g)
        glBindVertexArray(0)