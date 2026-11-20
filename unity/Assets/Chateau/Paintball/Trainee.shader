Shader "Chateau/Trainee"
{
    // Traînée des billes : non éclairée, couleur de sommet, fondu vers la queue et bords adoucis.
    Properties { _Intensite("Intensité",Float)=1.15 }
    SubShader
    {
        Tags { "RenderPipeline"="UniversalPipeline" "Queue"="Transparent" "RenderType"="Transparent" }
        Pass
        {
            Blend SrcAlpha OneMinusSrcAlpha
            ZWrite Off
            Cull Off
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
                half bord=1-abs(i.uv.y*2-1);
                half4 c=i.color;c.rgb=lerp(c.rgb,1,0.35*bord*bord)*_Intensite;c.a*=smoothstep(0,0.6,bord);
                return c;
            }
            ENDHLSL
        }
    }
}
