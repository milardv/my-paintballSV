Shader "Chateau/Fenetre"
{
    // Lumière d'une pièce vue de l'extérieur : panneau additif juste derrière le vitrage, face vers
    // l'extérieur (invisible depuis la pièce). Bords adoucis, plus clair vers le bas (lampes basses),
    // couleur de sommet × _Intensite.
    Properties { _Intensite("Intensité",Float)=1 }
    SubShader
    {
        Tags { "RenderPipeline"="UniversalPipeline" "Queue"="Transparent" "RenderType"="Transparent" "IgnoreProjector"="True" }
        Pass
        {
            Blend One One
            ZWrite Off
            Cull Back
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
            struct A { float4 positionOS:POSITION; float4 color:COLOR; float2 uv:TEXCOORD0; };
            struct V { float4 positionCS:SV_POSITION; half4 color:COLOR; float2 uv:TEXCOORD0; };
            CBUFFER_START(UnityPerMaterial)
            float _Intensite;
            CBUFFER_END
            V vert(A v) { V o;o.positionCS=TransformObjectToHClip(v.positionOS.xyz);o.color=v.color;o.uv=v.uv;return o; }
            half4 frag(V i):SV_Target
            {
                float2 u=i.uv;
                half bord=smoothstep(0,.14,u.x)*smoothstep(0,.14,1-u.x)*smoothstep(0,.06,u.y)*smoothstep(0,.12,1-u.y);
                half k=bord*(.55+.45*(1-u.y));
                return half4(i.color.rgb*k*_Intensite,0);
            }
            ENDHLSL
        }
    }
}
