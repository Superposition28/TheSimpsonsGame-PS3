using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEngine;

namespace RWReader
{
	[Serializable]
	public abstract class Section
	{
		public SectionHeader Header;
		public SectionDataStorage DataStorageType;
		public string Name;
		public bool CanHaveChildren;

		public int ID;

		public List<Section> Children = new();
		public Section Parent;

		[NonSerialized]
		public byte[] Raw;

		public abstract void Deserialize(BinaryReader reader);

		public T GetChild<T>() where T : Section
		{
			foreach (var child in Children)
			{
				if (child is T section)
				{
					return section;
				}
			}

			return null;
		}

		public List<T> GetChildren<T>() where T : Section
		{
			var children = new List<Section>();

			var nextChildren = new Stack<Section>(Children);

			while (nextChildren.Count > 0)
			{
				var child = nextChildren.Pop();

				children.Add(child);

				foreach (var item in child.Children)
				{
					nextChildren.Push(item);
				}
			}

			return children.OfType<T>().OrderBy(x => x.ID).ToList();
		}

		public T GetParent<T>() where T : Section
		{
			var currentParent = Parent;
			while (currentParent != null)
			{
				if (currentParent is T t)
				{
					return t;
				}

				currentParent = currentParent.Parent;
			}

			Debug.LogWarning($"Could not find parent of {Name} of type {typeof(T).Name}. Parent:{Parent.Name}, Grandparent:{Parent.Parent.Name}");
			return null;
		}

		public List<T> GetSibling<T>() where T : Section
		{
			if (Parent == null)
			{
				return new List<T>();
			}

			var ret = new List<T>();
			foreach (var child in Parent.Children)
			{
				if (child is T)
				{
					ret.Add((T)child);
				}
			}

			return ret;
		}
	}

	public enum SectionDataStorage
	{
		DataInSection,
		DataInStruct,
		NoData
	}
}
