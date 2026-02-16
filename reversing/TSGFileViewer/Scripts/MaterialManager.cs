using System;
using System.Collections.Generic;
using System.Text;
using Assets.Scripts.ResourceHandlers;
using Assets.Scripts.Resources;
using RWReader.Sections;
using UnityEngine;
using Material = UnityEngine.Material;
using Texture = RWReader.Sections.Texture;

namespace Assets.Scripts
{
    public class MaterialManager : MonoBehaviour
    {
		public static MaterialManager Instance { get; private set; }

		private static readonly int PaletteMap = Shader.PropertyToID("_PaletteMap");
		private static readonly int BaseMap = Shader.PropertyToID("_BaseMap");

		const uint RigidHash = 103326086;
		const uint RigidTexturedHash = 2566618050;
		const uint RigidDualTexturedHash = 3052503966;
		const uint RigidDualTexturedUVHash = 1913811202;
		const uint RigidGlossHash = 3408801425;
		const uint RigidMultitoneHash = 3052993522;
		const uint RigidNormalMapHash = 2345721244;
		const uint SkinHash = 1551361698;
		const uint SkinTexturedHash = 2084877734;
		const uint SkinDualTexturedHash = 3487979906;
		const uint SkinDualTexturedUVHash = 2866759198;
		const uint SkinGlossHash = 3120040365;
		const uint SkinFlipbookHash = 2596055507;
		const uint AAHash = 616457829;
		const uint AAColHash = 370176742;
		const uint AARowHash = 494099328;
		const uint EdgeHash = 3450081058;
		const uint EdgeAAHash = 2947266146;
		const uint FlipbookHash = 4214712379;
		const uint ProjTexHash = 1833805541;
		const uint ChocolateHash = 4204451511;
		const uint SkyHash = 2049395932;
		const uint UVHash = 617769830;
		const uint VFXRigidTexturedHash = 3879590297;

		public Shader Rigid;
	    public Shader RigidTextured;
	    public Shader RigidDualTextured;
	    public Shader RigidDualTexturedUV;
	    public Shader RigidGloss;
	    public Shader RigidMultitone;
	    public Shader RigidNormalMap;
	    public Shader Skin;
	    public Shader SkinTextured;
		public Shader SkinDualTextured;
		public Shader SkinDualTexturedUV;
		public Shader SkinGloss;
		public Shader SkinFlipbook;
		public Shader AA;
		public Shader AACol;
		public Shader AARow;
		public Shader Edge;
		public Shader EdgeAA;
		public Shader Flipbook;
		public Shader ProjTex;
		public Shader Chocolate;
		public Shader Sky;
		public Shader UV;
		public Shader VFXRigidTextured;

		private void Awake()
		{
			Instance = this;
		}

		public Shader GetShader(uint shaderID) =>
			shaderID switch
			{
				RigidHash => Rigid,
				RigidTexturedHash => RigidTextured,
				RigidDualTexturedHash => RigidDualTextured,
				RigidDualTexturedUVHash => RigidDualTexturedUV,
				RigidGlossHash => RigidGloss,
				RigidMultitoneHash => RigidMultitone,
				RigidNormalMapHash => RigidNormalMap,
				SkinHash => Skin,
				SkinTexturedHash => SkinTextured,
				SkinDualTexturedHash => SkinDualTextured,
				SkinDualTexturedUVHash => SkinDualTexturedUV,
				SkinGlossHash => SkinGloss,
				SkinFlipbookHash => SkinFlipbook,
				AAHash => AA,
				AAColHash => AACol,
				AARowHash => AARow,
				EdgeHash => Edge,
				EdgeAAHash => EdgeAA,
				FlipbookHash => Flipbook,
				ProjTexHash => ProjTex,
				ChocolateHash => Chocolate,
				SkyHash => Sky,
				UVHash => UV,
				VFXRigidTexturedHash => VFXRigidTextured,
				_ => throw new NotImplementedException($"{shaderID} not found")
			};

		public Material CreateMaterialInstance(uint shaderID, params Texture2D[] textures)
		{
			var shader = GetShader(shaderID);

			var material = new Material(shader);

			if (textures.Length == 0)
			{
				Debug.LogWarning("No textures given to material creation...");
				return material;
			}

			switch (shaderID)
			{
				case SkinHash:
				case RigidHash:
					material.SetTexture(PaletteMap, textures[0]);
					break;

				case SkinTexturedHash:
				case RigidTexturedHash:
					if (textures.Length == 1)
					{
						material.SetTexture(BaseMap, textures[0]);
					}
					else
					{
						material.SetTexture(PaletteMap, textures[0]);
						material.SetTexture(BaseMap, textures[1]);
					}
					break;

				case SkinDualTexturedHash:
				case RigidDualTexturedHash:
					if (textures.Length == 1)
					{
						material.SetTexture("_Tex0", textures[0]);
					}
					else
					{
						material.SetTexture("_Tex0", textures[0]);
						material.SetTexture("_Tex1", textures[1]);
					}
					break;

				case SkinDualTexturedUVHash:
				case RigidDualTexturedUVHash:
					if (textures.Length == 1)
					{
						material.SetTexture("_Tex0", textures[0]);
					}
					else
					{
						material.SetTexture("_Tex0", textures[0]);
						material.SetTexture("_Tex1", textures[1]);
					}
					break;

				case UVHash:
					material.SetTexture(BaseMap, textures[0]);
					break;

				case RigidMultitoneHash:
					if (textures.Length == 1)
					{
						material.SetTexture("_Tex0", textures[0]);
					}
					else
					{
						material.SetTexture("_Tex0", textures[0]);
						material.SetTexture("_Tex1", textures[1]);
					}

					break;
			}

			return material;
		}

		public Texture2D[] GetTextures(RWReader.Sections.Material material)
		{
			var returnTextures = new List<Texture2D>();

			var textureSections = material.GetChildren<Texture>();
			foreach (var texture in textureSections)
			{
				var texName = texture.GetTextureName();
				var textureNative = GetTextureNative(texName);

				returnTextures.Add(textureNative?.Texture);
			}

			return returnTextures.ToArray();
		}

		public TextureNative GetTextureNative(string textureName)
		{
			var textureDicts = ResourceHandlerManager.GetResources<rwID_TEXDICTIONARY>();

			foreach (var texDict in textureDicts)
			{
				foreach (var texture in texDict.SectionTree.GetChildren<TextureNative>())
				{
					if (texture.TextureName == textureName)
					{
						return texture;
					}
				}
			}

			Debug.LogWarning($"Couldn't find a texture with name {textureName}");
			return null;
		}
    }
}
