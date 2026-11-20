Shader "Chateau/Peinture"
{
    Properties { _BaseMap("Eclaboussure",2D)="white" {} _BaseColor("Couleur",Color)=(1,0,1,1) }
    SubShader
    {
        Tags { "RenderPipeline"="UniversalPipeline" "Queue"="Transparent" "RenderType"="Transparent" }
        Pass
        {
            Blend SrcAlpha OneMinusSrcAlpha
            ZWrite Off
            Cull Off
            Offset -1,-1
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
            struct A { float4 positionOS:POSITION; float2 uv:TEXCOORD0; };
            struct V { float4 positionCS:SV_POSITION; float2 uv:TEXCOORD0; };
            TEXTURE2D(_BaseMap); SAMPLER(sampler_BaseMap);
            CBUFFER_START(UnityPerMaterial)
            float4 _BaseColor;
            CBUFFER_END
            V vert(A v) { V o;o.positionCS=TransformObjectToHClip(v.positionOS.xyz);o.uv=v.uv;return o; }
            half4 frag(V i):SV_Target { half4 t=SAMPLE_TEXTURE2D(_BaseMap,sampler_BaseMap,i.uv);return half4(_BaseColor.rgb,t.a*_BaseColor.a); }
            ENDHLSL
        }
    }
}
