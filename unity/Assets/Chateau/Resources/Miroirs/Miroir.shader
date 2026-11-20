// Miroir plan : échantillonne en espace écran le rendu de la caméra réfléchie (Miroirs.cs). La caméra de reflet
// est une caméra ordinaire posée au symétrique de la caméra du joueur ; son image est le reflet retourné
// horizontalement, d'où u = 1 - u.
Shader "Chateau/Miroir"
{
    Properties
    {
        _ReflectionTex ("Reflet", 2D) = "black" {}
        _Teinte ("Teinte du tain", Color) = (0.93, 0.94, 0.92, 1)
    }
    SubShader
    {
        Tags { "RenderType" = "Opaque" "RenderPipeline" = "UniversalPipeline" "Queue" = "Geometry" }
        Pass
        {
            Name "Miroir"
            Tags { "LightMode" = "UniversalForward" }
            Cull Off
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"

            TEXTURE2D(_ReflectionTex);
            SAMPLER(sampler_ReflectionTex);
            CBUFFER_START(UnityPerMaterial)
                float4 _ReflectionTex_ST;
                half4 _Teinte;
            CBUFFER_END

            struct Attributes { float4 positionOS : POSITION; };
            struct Varyings { float4 positionCS : SV_POSITION; float4 ecran : TEXCOORD0; };

            Varyings vert (Attributes v)
            {
                Varyings o;
                o.positionCS = TransformObjectToHClip(v.positionOS.xyz);
                o.ecran = ComputeScreenPos(o.positionCS);
                return o;
            }

            half4 frag (Varyings i) : SV_Target
            {
                float2 uv = i.ecran.xy / i.ecran.w;
                uv.x = 1.0 - uv.x;
                return SAMPLE_TEXTURE2D(_ReflectionTex, sampler_ReflectionTex, uv) * _Teinte;
            }
            ENDHLSL
        }
    }
}
