Shader "Chateau/Lumineux"
{
    // Surfaces qui émettent leur propre lumière (ampoules, papier des lanternes, abat-jour allumés) :
    // non éclairées, couleur de sommet (si _Sommets = 1) multipliée par _BaseColor et _Intensite.
    Properties { _BaseColor("Couleur",Color)=(1,1,1,1) _Intensite("Intensité",Float)=1 _Sommets("Couleur de sommet",Float)=1 }
    SubShader
    {
        Tags { "RenderPipeline"="UniversalPipeline" "Queue"="Geometry" "RenderType"="Opaque" }
        Pass
        {
            Cull Off
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
            struct A { float4 positionOS:POSITION; float4 color:COLOR; };
            struct V { float4 positionCS:SV_POSITION; half4 color:COLOR; };
            CBUFFER_START(UnityPerMaterial)
            float4 _BaseColor; float _Intensite; float _Sommets;
            CBUFFER_END
            V vert(A v) { V o;o.positionCS=TransformObjectToHClip(v.positionOS.xyz);o.color=lerp(half4(1,1,1,1),v.color,_Sommets);return o; }
            half4 frag(V i):SV_Target { return half4(i.color.rgb*_BaseColor.rgb*_Intensite,1); }
            ENDHLSL
        }
    }
}
