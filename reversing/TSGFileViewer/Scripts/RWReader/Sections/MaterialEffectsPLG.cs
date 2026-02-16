using System;
using System.IO;

namespace RWReader.Sections
{
	[Serializable]
	internal class MaterialEffectsPLG : Section
	{
		public MaterialEffectsPLG()
		{
			Name = "Material Effects PLG";
			Header.ClumpID = 0x00000120;
			DataStorageType = SectionDataStorage.DataInSection;
			CanHaveChildren = false;
		}

		public bool MatFXEnabled;

		public MaterialEffect Type;
		public Effect EffectOne;
		public Effect EffectTwo;

		public override void Deserialize(BinaryReader reader)
		{
			if (Parent.Parent is Atomic)
			{
				MatFXEnabled = reader.ReadBool32();
				return;
			}

			Type = (MaterialEffect)reader.ReadInt32();
			EffectOne = ReadEffect(reader);
			EffectTwo = ReadEffect(reader);
		}

		private Effect ReadEffect(BinaryReader reader)
		{
			var type = (MaterialEffect)reader.ReadInt32();

			if (type == MaterialEffect.Null)
			{
				return new NoEffect();
			}

			if (type == MaterialEffect.Bumpmap)
			{
				var effect = new BumpMappingEffect();
				effect.Intensity = reader.ReadSingle();
				effect.ContainsBumpMap = reader.ReadBool32();
				if (effect.ContainsBumpMap)
				{
					effect.BumpMap = ReadTexture(reader);
				}

				effect.ContainsHeightMap = reader.ReadBool32();
				if (effect.ContainsHeightMap)
				{
					effect.HeightMap = ReadTexture(reader);
				}

				return effect;
			}

			if (type == MaterialEffect.Envmap)
			{
				var effect = new EnvironmentMapping();
				effect.ReflectionCoefficient = reader.ReadSingle();
				effect.UseFrameBufferAlphaChannel = reader.ReadBool32();
				effect.ContainsEnvMap = reader.ReadBool32();
				if (effect.ContainsEnvMap)
				{
					effect.EnvMap = ReadTexture(reader);
				}

				return effect;
			}

			if (type == MaterialEffect.Dual)
			{
				var effect = new DualTexturingEffect();
				effect.SourceBlendMode = (BlendMode)reader.ReadInt32();
				effect.DestBlendMode = (BlendMode)reader.ReadInt32();
				effect.ContainsTexture = reader.ReadBool32();

				if (effect.ContainsTexture)
				{
					effect.Texture = ReadTexture(reader);
				}

				return effect;
			}

			if (type == MaterialEffect.UVTransform)
			{
				return new UVAnimationEffect();
			}

			throw new NotImplementedException();
		}

		private Texture ReadTexture(BinaryReader reader)
		{
			var streamReader = new RWStreamReader();
			var texture = (Texture)streamReader.ReadSection(reader, this);
			Children.Add(texture);
			return texture;
		}

		public enum MaterialEffect
		{
			Null,
			Bumpmap,
			Envmap,
			Bumpenvmap,
			Dual,
			UVTransform,
			DualUVTransform
		}

		public abstract class Effect
		{
			public virtual MaterialEffect Type => MaterialEffect.Null;
		}

		public class NoEffect : Effect
		{
		}

		public class BumpMappingEffect : Effect
		{
			public override MaterialEffect Type => MaterialEffect.Bumpmap;

			public float Intensity;
			public bool ContainsBumpMap;
			public Texture BumpMap;
			public bool ContainsHeightMap;
			public Texture HeightMap;
		}

		public class EnvironmentMapping : Effect
		{
			public override MaterialEffect Type => MaterialEffect.Envmap;

			public float ReflectionCoefficient;
			public bool UseFrameBufferAlphaChannel;
			public bool ContainsEnvMap;
			public Texture EnvMap;
		}

		public class DualTexturingEffect : Effect
		{
			public override MaterialEffect Type => MaterialEffect.Dual;

			public BlendMode SourceBlendMode;
			public BlendMode DestBlendMode;
			public bool ContainsTexture;
			public Texture Texture;
		}

		public class UVAnimationEffect : Effect
		{
			public override MaterialEffect Type => MaterialEffect.UVTransform;
		}

		public enum BlendMode
		{
			NoBlend,
			Zero,
			One,
			SrcColor,
			InvSrcColor,
			SrcAlpha,
			InvSrcAlpha,
			DestAlpha,
			InvDestAlpha,
			DestColor,
			InvDestColor,
			SrcAlphaSat
		}
	}


}