Shader "Chateau/Halo"
{
    // Halos des ampoules : quadrilatères tournés vers la caméra dans le vertex shader. Chaque sommet porte le
    // centre du halo (position), son coin (uv, -1..1) et sa taille (uv2.x). Mélange additif : cœur vif et
    // auréole douce, à la couleur de sommet, multipliés par _Intensite (0 le jour).
    Properties { _Intensite("Intensité",Float)=1 }
    SubShader
    {
        Tags { "RenderPipeline"="UniversalPipeline" "Queue"="Transparent" "RenderType"="Transparent" "IgnoreProjector"="True" }
        Pass
        {
            Blend One One
            ZWrite Off
            Cull Off
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
            struct A { float4 positionOS:POSITION; float4 color:COLOR; float2 uv:TEXCOORD0; float2 uv2:TEXCOORD1; };
            struct V { float4 positionCS:SV_POSITION; half4 color:COLOR; float2 uv:TEXCOORD0; };
            CBUFFER_START(UnityPerMaterial)
            float _Intensite;
            CBUFFER_END
            V vert(A v)
            {
                V o;
                float3 centre=TransformWorldToView(TransformObjectToWorld(v.positionOS.xyz));
                centre.xy+=v.uv*v.uv2.x;
                o.positionCS=TransformWViewToHClip(centre);o.color=v.color;o.uv=v.uv;return o;
            }
            half4 frag(V i):SV_Target
            {
                float r2=dot(i.uv,i.uv);
                half k=exp(-r2*40)*1.6+exp(-r2*5)*.35*saturate(1-r2);
                return half4(i.color.rgb*k*_Intensite,0);
            }
            ENDHLSL
        }
    }
}
