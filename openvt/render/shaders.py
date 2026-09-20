VERT = """
#version 330 core
layout(location = 0) in vec2 in_pos;
layout(location = 1) in vec2 in_uv;
uniform mat3 u_proj;
out vec2 v_uv;
void main() {
    vec3 p = u_proj * vec3(in_pos, 1.0);
    gl_Position = vec4(p.xy, 0.0, 1.0);
    v_uv = in_uv;
}
"""

FRAG = """
#version 330 core
in vec2 v_uv;
uniform sampler2D u_tex;
uniform sampler2D u_mask;
uniform int   u_use_mask;
uniform float u_opacity;
uniform vec4  u_tint;
uniform vec2  u_screen;
out vec4 frag;
void main() {
    vec4 c = texture(u_tex, v_uv) * u_tint;
    c.a *= u_opacity;
    if (u_use_mask == 1) {
        c.a *= texture(u_mask, gl_FragCoord.xy / u_screen).a;
    }
    frag = vec4(c.rgb * c.a, c.a);   // premultiplied alpha out
}
"""